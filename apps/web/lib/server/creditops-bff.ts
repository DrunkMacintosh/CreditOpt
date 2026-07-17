// The future identity callback must issue this with HttpOnly, Secure,
// SameSite=Strict, Path=/, and no Domain. This BFF never issues the token cookie.
export const SESSION_COOKIE_NAME = "__Host-creditops-workforce";
export const CSRF_COOKIE_NAME = "__Host-creditops-csrf";
export const CSRF_HEADER_NAME = "x-creditops-csrf";

const MAX_REQUEST_BYTES = 1024 * 1024;
const MAX_RESPONSE_BYTES = 2 * 1024 * 1024;
const SAFE_RESPONSE_HEADERS = ["content-type", "retry-after", "x-request-id"];
const SAFE_ID = /^[A-Za-z0-9_-]+$/;

interface ProxyDependencies {
  fetcher?: typeof fetch;
  upstreamBaseUrl?: string;
}

export async function proxyCreditOpsRequest(
  request: Request,
  pathSegments: string[],
  dependencies: ProxyDependencies = {},
): Promise<Response> {
  const method = request.method.toUpperCase();
  if (!allowlisted(method, pathSegments)) {
    return jsonError(404, "BFF_ROUTE_NOT_ALLOWED");
  }

  const token = readCookie(request.headers.get("cookie"), SESSION_COOKIE_NAME);
  if (!validCredential(token)) {
    return jsonError(401, "SESSION_REQUIRED");
  }

  const hasBody = method !== "GET" && method !== "HEAD";
  if (hasBody) {
    const mediaType = (request.headers.get("content-type") ?? "")
      .split(";", 1)[0]
      .trim()
      .toLowerCase();
    if (mediaType !== "application/json") {
      return jsonError(415, "JSON_BODY_REQUIRED");
    }
    if (!validCsrf(request)) {
      return jsonError(403, "CSRF_VALIDATION_FAILED");
    }
  }

  const idempotencyKey = request.headers.get("idempotency-key");
  if (
    isUploadCompletion(method, pathSegments) &&
    (!validOpaqueHeader(idempotencyKey) || idempotencyKey.length > 256)
  ) {
    return jsonError(400, "IDEMPOTENCY_KEY_REQUIRED");
  }

  const configuredBase = dependencies.upstreamBaseUrl ?? process.env.CREDITOPS_API_URL;
  const upstreamBase = parseUpstreamBase(configuredBase);
  if (!upstreamBase) {
    return jsonError(503, "UPSTREAM_NOT_CONFIGURED");
  }

  let body: string | undefined;
  if (hasBody) {
    const declaredLength = Number(request.headers.get("content-length"));
    if (Number.isFinite(declaredLength) && declaredLength > MAX_REQUEST_BYTES) {
      return jsonError(413, "JSON_BODY_TOO_LARGE");
    }
    body = await request.text();
    if (new TextEncoder().encode(body).byteLength > MAX_REQUEST_BYTES) {
      return jsonError(413, "JSON_BODY_TOO_LARGE");
    }
  }

  const upstreamHeaders = new Headers({
    accept: "application/json",
    authorization: `Bearer ${token}`,
  });
  if (hasBody) upstreamHeaders.set("content-type", "application/json");
  if (idempotencyKey && validOpaqueHeader(idempotencyKey)) {
    upstreamHeaders.set("idempotency-key", idempotencyKey);
  }

  const incomingUrl = new URL(request.url);
  const upstreamUrl = new URL(`/${pathSegments.join("/")}`, upstreamBase);
  upstreamUrl.search = incomingUrl.search;

  let upstreamResponse: Response;
  try {
    upstreamResponse = await (dependencies.fetcher ?? fetch)(upstreamUrl.toString(), {
      method,
      headers: upstreamHeaders,
      body,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return jsonError(502, "UPSTREAM_UNAVAILABLE");
  }

  const responseType = upstreamResponse.headers.get("content-type") ?? "";
  if (!responseType.toLowerCase().includes("application/json")) {
    return jsonError(502, "UPSTREAM_NON_JSON_RESPONSE");
  }
  const responseBody = await upstreamResponse.arrayBuffer();
  if (responseBody.byteLength > MAX_RESPONSE_BYTES) {
    return jsonError(502, "UPSTREAM_RESPONSE_TOO_LARGE");
  }

  const responseHeaders = new Headers({ "cache-control": "no-store" });
  for (const name of SAFE_RESPONSE_HEADERS) {
    const value = upstreamResponse.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  return new Response(responseBody, {
    status: upstreamResponse.status,
    headers: responseHeaders,
  });
}

function isUploadCompletion(method: string, segments: string[]): boolean {
  return (
    method === "POST" &&
    segments.length === 5 &&
    segments[0] === "api" &&
    segments[1] === "v1" &&
    segments[2] === "upload-intents" &&
    SAFE_ID.test(segments[3]) &&
    segments[4] === "complete"
  );
}

function allowlisted(method: string, segments: string[]): boolean {
  if (segments.some((segment) => !SAFE_ID.test(segment))) return false;
  const path = `/${segments.join("/")}`;
  return (
    (method === "GET" && path === "/api/v1/cases") ||
    (method === "POST" && path === "/api/v1/cases") ||
    (method === "GET" && /^\/api\/v1\/cases\/[A-Za-z0-9_-]+$/.test(path)) ||
    (method === "POST" && /^\/api\/v1\/cases\/[A-Za-z0-9_-]+\/upload-intents$/.test(path)) ||
    (method === "POST" && /^\/api\/v1\/upload-intents\/[A-Za-z0-9_-]+\/complete$/.test(path)) ||
    (method === "GET" && /^\/api\/v1\/tasks\/[A-Za-z0-9_-]+$/.test(path))
  );
}

function validCsrf(request: Request): boolean {
  const requestOrigin = request.headers.get("origin");
  const expectedOrigin = new URL(request.url).origin;
  const fetchSite = request.headers.get("sec-fetch-site");
  if (requestOrigin !== expectedOrigin || (fetchSite && fetchSite !== "same-origin")) {
    return false;
  }
  const cookieToken = readCookie(request.headers.get("cookie"), CSRF_COOKIE_NAME);
  const headerToken = request.headers.get(CSRF_HEADER_NAME);
  return (
    validOpaqueHeader(cookieToken) &&
    validOpaqueHeader(headerToken) &&
    cookieToken === headerToken
  );
}

function readCookie(header: string | null, name: string): string | null {
  for (const part of (header ?? "").split(";")) {
    const index = part.indexOf("=");
    if (index < 0 || part.slice(0, index).trim() !== name) continue;
    const rawValue = part.slice(index + 1).trim();
    try {
      return decodeURIComponent(rawValue);
    } catch {
      return null;
    }
  }
  return null;
}

function validCredential(value: string | null): value is string {
  return validOpaqueHeader(value) && value.length <= 8192;
}

function validOpaqueHeader(value: string | null): value is string {
  return typeof value === "string" && value.length > 0 && !/[\r\n\0]/.test(value);
}

function parseUpstreamBase(value: string | undefined): URL | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password) return null;
    url.pathname = `${url.pathname.replace(/\/$/, "")}/`;
    url.search = "";
    url.hash = "";
    return url;
  } catch {
    return null;
  }
}

function jsonError(status: number, code: string): Response {
  return Response.json(
    {
      code,
      messageVi: "Không thể hoàn tất yêu cầu.",
      correlationId: null,
      retryable: status >= 500,
    },
    { status, headers: { "cache-control": "no-store" } },
  );
}
