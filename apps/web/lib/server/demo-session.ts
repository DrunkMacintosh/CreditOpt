// BFF-local anonymous demo-session minting.
//
// A judge clicks the landing-page CTA; the browser POSTs here with credentials
// but no session cookie yet (this endpoint is what MINTS that cookie). This
// module exchanges the Google Cloud Run OIDC id token (via
// getCloudRunServerlessAuthorization, audienced to the API origin — the same
// mechanism the JSON proxy in creditops-bff.ts uses) for a synthetic actor
// session from the API's POST /api/v1/demo-sessions, then sets the SAME
// first-party cookies the rest of the BFF already trusts
// (SESSION_COOKIE_NAME / CSRF_COOKIE_NAME from creditops-bff.ts) so the judge
// lands in the working app with a real, RLS-scoped session — never a mocked
// one. If the API is unreachable, misconfigured, rate-limited, or returns a
// payload that does not match the documented shape, this fails closed with a
// sanitized error; it never fabricates a session.
//
// Self-contained like lib/api/orchestration.ts: this module re-implements its
// own small bounded-read / response-shape helpers rather than reaching into
// creditops-bff.ts internals, borrowing only its two exported cookie-name
// constants so the two modules can never disagree on what the rest of the BFF
// reads back out of the cookie jar.

import { getCloudRunServerlessAuthorization } from "./cloud-run-auth";
import { CSRF_COOKIE_NAME, SESSION_COOKIE_NAME } from "./creditops-bff";

const MAX_RESPONSE_BYTES = 8 * 1024;
const MAX_SESSION_TOKEN_LEN = 8192;
const MIN_TTL_SECONDS = 60;
const MAX_TTL_SECONDS = 24 * 60 * 60;
const MAX_ROLES = 20;
const MAX_ROLE_LEN = 64;
const MAX_DISCLAIMER_LEN = 2000;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ROLE_PATTERN = /^[A-Za-z_]+$/;

export interface DemoSessionDependencies {
  fetcher?: typeof fetch;
  upstreamBaseUrl?: string;
  serverlessAuthorization?: (request: Request) => Promise<string>;
  randomCsrfToken?: () => string;
}

interface ParsedDemoSession {
  sessionToken: string;
  expiresInSeconds: number;
  caseId: string;
}

export async function mintDemoSession(
  request: Request,
  dependencies: DemoSessionDependencies = {},
): Promise<Response> {
  if (!sameOriginRequest(request)) {
    return jsonError(403, "ORIGIN_REJECTED");
  }

  const upstreamBase = parseUpstreamBase(
    dependencies.upstreamBaseUrl ?? process.env.CREDITOPS_API_URL,
  );
  if (!upstreamBase) return jsonError(503, "UPSTREAM_NOT_CONFIGURED");

  let serverlessToken: string;
  try {
    serverlessToken = await (
      dependencies.serverlessAuthorization ??
      ((incoming: Request) =>
        getCloudRunServerlessAuthorization(incoming, { audience: upstreamBase.origin }))
    )(request);
  } catch {
    return jsonError(503, "CLOUD_RUN_AUTH_NOT_CONFIGURED");
  }

  const upstreamUrl = new URL("/api/v1/demo-sessions", upstreamBase);
  let upstreamResponse: Response;
  try {
    upstreamResponse = await (dependencies.fetcher ?? fetch)(upstreamUrl.toString(), {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
        authorization: `Bearer ${serverlessToken}`,
      },
      body: "{}",
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return jsonError(502, "UPSTREAM_UNAVAILABLE");
  }

  if (upstreamResponse.status === 429) {
    return relayRateLimit(upstreamResponse);
  }

  if (upstreamResponse.status !== 201) {
    await cancelBody(upstreamResponse.body);
    return jsonError(502, "DEMO_SESSION_UPSTREAM_ERROR");
  }

  const contentType = upstreamResponse.headers.get("content-type") ?? "";
  if (!isJsonMediaType(contentType)) {
    await cancelBody(upstreamResponse.body);
    return jsonError(502, "UPSTREAM_NON_JSON_RESPONSE");
  }
  if (declaredTooLarge(upstreamResponse.headers)) {
    await cancelBody(upstreamResponse.body);
    return jsonError(502, "UPSTREAM_RESPONSE_TOO_LARGE");
  }

  let bytes: Uint8Array | null;
  try {
    bytes = await readBounded(upstreamResponse.body, MAX_RESPONSE_BYTES);
  } catch {
    return jsonError(502, "UPSTREAM_RESPONSE_UNREADABLE");
  }
  if (bytes === null) return jsonError(502, "UPSTREAM_RESPONSE_TOO_LARGE");

  const parsed = parseDemoSession(bytes);
  if (parsed === null) return jsonError(502, "DEMO_SESSION_RESPONSE_INVALID");

  const csrfToken = (dependencies.randomCsrfToken ?? randomOpaqueToken)();
  const headers = new Headers({
    "content-type": "application/json",
    "cache-control": "no-store",
  });
  headers.append(
    "set-cookie",
    cookieString(SESSION_COOKIE_NAME, parsed.sessionToken, parsed.expiresInSeconds, true),
  );
  headers.append(
    "set-cookie",
    cookieString(CSRF_COOKIE_NAME, csrfToken, parsed.expiresInSeconds, false),
  );
  return new Response(JSON.stringify({ caseId: parsed.caseId }), {
    status: 201,
    headers,
  });
}

async function relayRateLimit(upstreamResponse: Response): Promise<Response> {
  const retryAfter = upstreamResponse.headers.get("retry-after");
  await cancelBody(upstreamResponse.body);
  const headers = new Headers({
    "content-type": "application/json",
    "cache-control": "no-store",
  });
  if (retryAfter !== null && /^\d+$/.test(retryAfter)) {
    headers.set("retry-after", retryAfter);
  }
  return new Response(
    JSON.stringify({
      code: "DEMO_SESSION_RATE_LIMITED",
      messageVi: "Hệ thống đang giới hạn số phiên demo khởi tạo. Vui lòng thử lại sau.",
      correlationId: null,
      retryable: true,
    }),
    { status: 429, headers },
  );
}

// Only a same-origin fetch may mint a session cookie for this browser. A
// missing Origin header (no unsafe-method request omits it in practice) fails
// closed rather than being treated as trusted.
function sameOriginRequest(request: Request): boolean {
  const origin = request.headers.get("origin");
  const expectedOrigin = new URL(request.url).origin;
  const fetchSite = request.headers.get("sec-fetch-site");
  return origin === expectedOrigin && (fetchSite === null || fetchSite === "same-origin");
}

function cookieString(
  name: string,
  value: string,
  maxAgeSeconds: number,
  httpOnly: boolean,
): string {
  const attributes = [`${name}=${value}`, "Path=/", "Secure", "SameSite=Lax", `Max-Age=${maxAgeSeconds}`];
  if (httpOnly) attributes.splice(1, 0, "HttpOnly");
  return attributes.join("; ");
}

// Rebuilds the trusted fields field-by-field from the API's documented
// DemoSessionResponse shape; anything undeclared, mistyped, or out of range
// fails closed to null rather than being forwarded or trusted.
function parseDemoSession(bytes: Uint8Array): ParsedDemoSession | null {
  let value: unknown;
  try {
    value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    return null;
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const raw = value as Record<string, unknown>;

  const sessionToken = raw.sessionToken;
  if (
    typeof sessionToken !== "string" ||
    sessionToken.length === 0 ||
    sessionToken.length > MAX_SESSION_TOKEN_LEN ||
    /[\r\n\0;]/.test(sessionToken)
  ) {
    return null;
  }

  if (raw.tokenType !== "Bearer") return null;

  const expiresInSeconds = raw.expiresInSeconds;
  if (
    typeof expiresInSeconds !== "number" ||
    !Number.isInteger(expiresInSeconds) ||
    expiresInSeconds < MIN_TTL_SECONDS ||
    expiresInSeconds > MAX_TTL_SECONDS
  ) {
    return null;
  }

  const actorId = raw.actorId;
  if (typeof actorId !== "string" || !UUID.test(actorId)) return null;

  const caseId = raw.caseId;
  if (typeof caseId !== "string" || !UUID.test(caseId)) return null;

  const roles = raw.roles;
  if (
    !Array.isArray(roles) ||
    roles.length < 1 ||
    roles.length > MAX_ROLES ||
    roles.some(
      (role) =>
        typeof role !== "string" ||
        role.length === 0 ||
        role.length > MAX_ROLE_LEN ||
        !ROLE_PATTERN.test(role),
    )
  ) {
    return null;
  }

  const disclaimer = raw.disclaimer;
  if (
    typeof disclaimer !== "string" ||
    disclaimer.length === 0 ||
    disclaimer.length > MAX_DISCLAIMER_LEN
  ) {
    return null;
  }

  return { sessionToken, expiresInSeconds, caseId: caseId.toLowerCase() };
}

async function readBounded(
  stream: ReadableStream<Uint8Array<ArrayBufferLike>> | null,
  limit: number,
): Promise<Uint8Array | null> {
  if (!stream) return new Uint8Array();
  const reader = stream.getReader();
  const chunks: Uint8Array<ArrayBufferLike>[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > limit) {
        try {
          await reader.cancel("body-size-limit");
        } catch {
          // The limit decision is authoritative even if the peer cannot cancel.
        }
        return null;
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const result = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return result;
}

async function cancelBody(stream: ReadableStream<Uint8Array<ArrayBufferLike>> | null): Promise<void> {
  if (!stream || stream.locked) return;
  try {
    await stream.cancel("response-rejected");
  } catch {
    // The response is already being discarded; never expose provider details.
  }
}

function declaredTooLarge(headers: Headers): boolean {
  const raw = headers.get("content-length");
  if (raw === null || !/^\d+$/.test(raw)) return false;
  const declared = Number(raw);
  return Number.isSafeInteger(declared) && declared > MAX_RESPONSE_BYTES;
}

function isJsonMediaType(value: string): boolean {
  return value.split(";", 1)[0].trim().toLowerCase() === "application/json";
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

function randomOpaqueToken(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID().replace(/-/g, "");
  }
  const bytes = new Uint8Array(32);
  globalThis.crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function jsonError(status: number, code: string): Response {
  return Response.json(
    {
      code,
      messageVi: "Không thể khởi tạo phiên demo. Vui lòng thử lại.",
      correlationId: null,
      retryable: status >= 500,
    },
    { status, headers: { "cache-control": "no-store" } },
  );
}
