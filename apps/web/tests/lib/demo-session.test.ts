import { describe, expect, it, vi } from "vitest";

import {
  CSRF_COOKIE_NAME,
  SESSION_COOKIE_NAME,
} from "../../lib/server/creditops-bff";
import { mintDemoSession as mintDemoSessionImpl } from "../../lib/server/demo-session";

const upstreamBaseUrl = "https://creditops-api.invalid";

function mintDemoSession(
  request: Request,
  dependencies: Parameters<typeof mintDemoSessionImpl>[1] = {},
) {
  return mintDemoSessionImpl(request, {
    serverlessAuthorization: async () => "test-cloud-run-id-token",
    upstreamBaseUrl,
    ...dependencies,
  });
}

function request(init: RequestInit = {}, origin = "https://app.invalid") {
  const headers = new Headers(init.headers);
  if (origin) headers.set("origin", origin);
  return new Request("https://app.invalid/api/demo-session", {
    method: "POST",
    ...init,
    headers,
  });
}

const validDemoSessionBody = {
  sessionToken: "header.payload.signature",
  tokenType: "Bearer",
  expiresInSeconds: 3600,
  actorId: "123e4567-e89b-12d3-a456-426614174000",
  caseId: "223E4567-E89B-12D3-A456-426614174001",
  roles: ["RELATIONSHIP_INTAKE"],
  disclaimer: "Dữ liệu tổng hợp — không phải hồ sơ khách hàng thật.",
};

function upstreamJson(body: unknown, status = 201): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function getSetCookies(response: Response): string[] {
  const raw = (response.headers as unknown as { getSetCookie?: () => string[] }).getSetCookie;
  if (typeof raw === "function") return raw.call(response.headers);
  const single = response.headers.get("set-cookie");
  return single ? [single] : [];
}

describe("demo-session minting", () => {
  it("fails closed when Cloud Run IAM authorization is not configured", async () => {
    const fetcher = vi.fn();
    const response = await mintDemoSessionImpl(request(), {
      fetcher,
      upstreamBaseUrl,
    });

    expect(response.status).toBe(503);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("fails closed when the upstream API base is not configured", async () => {
    const fetcher = vi.fn();
    const response = await mintDemoSession(request(), {
      fetcher,
      upstreamBaseUrl: undefined,
    });

    expect(response.status).toBe(503);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("rejects a cross-origin mint request", async () => {
    const fetcher = vi.fn();
    const response = await mintDemoSession(
      request({}, "https://evil.invalid"),
      { fetcher },
    );

    expect(response.status).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("mints a demo session, sets first-party cookies, and returns only the caseId", async () => {
    const fetcher = vi.fn().mockResolvedValue(upstreamJson(validDemoSessionBody));

    const response = await mintDemoSession(request(), { fetcher });

    expect(response.status).toBe(201);
    expect(await response.json()).toEqual({
      caseId: "223e4567-e89b-12d3-a456-426614174001",
    });

    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe(`${upstreamBaseUrl}/api/v1/demo-sessions`);
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("authorization")).toBe(
      "Bearer test-cloud-run-id-token",
    );
    expect(init.body).toBe("{}");

    const cookies = getSetCookies(response);
    const sessionCookie = cookies.find((cookie) => cookie.startsWith(`${SESSION_COOKIE_NAME}=`));
    const csrfCookie = cookies.find((cookie) => cookie.startsWith(`${CSRF_COOKIE_NAME}=`));
    expect(sessionCookie).toBeDefined();
    expect(sessionCookie).toContain("header.payload.signature");
    expect(sessionCookie).toContain("HttpOnly");
    expect(sessionCookie).toContain("Secure");
    expect(sessionCookie).toContain("SameSite=Lax");
    expect(sessionCookie).toContain("Path=/");
    expect(sessionCookie).toContain("Max-Age=3600");

    expect(csrfCookie).toBeDefined();
    expect(csrfCookie).not.toContain("HttpOnly");
    expect(csrfCookie).toContain("Secure");
    expect(csrfCookie).toContain("SameSite=Lax");
    expect(csrfCookie).toContain("Max-Age=3600");
  });

  it("relays a 429 from the API without leaking upstream response details", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ secret: "upstream-detail" }), {
        status: 429,
        headers: { "content-type": "application/json", "retry-after": "5" },
      }),
    );

    const response = await mintDemoSession(request(), { fetcher });

    expect(response.status).toBe(429);
    expect(response.headers.get("retry-after")).toBe("5");
    const body = (await response.json()) as Record<string, unknown>;
    expect(body.code).toBe("DEMO_SESSION_RATE_LIMITED");
    expect(JSON.stringify(body)).not.toContain("upstream-detail");
  });

  it("fails closed on a non-201 upstream response without exposing its body", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "internal trace" }), {
        status: 500,
        headers: { "content-type": "application/json" },
      }),
    );

    const response = await mintDemoSession(request(), { fetcher });

    expect(response.status).toBe(502);
    const text = JSON.stringify(await response.json());
    expect(text).not.toContain("internal trace");
  });

  it.each([
    { ...validDemoSessionBody, tokenType: "Basic" },
    { ...validDemoSessionBody, roles: [] },
    { ...validDemoSessionBody, caseId: "not-a-uuid" },
    { ...validDemoSessionBody, expiresInSeconds: 0 },
    { ...validDemoSessionBody, sessionToken: "" },
  ])("fails closed on a malformed demo-session payload %#", async (payload) => {
    const fetcher = vi.fn().mockResolvedValue(upstreamJson(payload));
    const response = await mintDemoSession(request(), { fetcher });

    expect(response.status).toBe(502);
    expect(getSetCookies(response)).toHaveLength(0);
  });

  it("fails closed on a non-JSON upstream response", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response("<html>not json</html>", {
        status: 201,
        headers: { "content-type": "text/html" },
      }),
    );
    const response = await mintDemoSession(request(), { fetcher });

    expect(response.status).toBe(502);
  });

  it("never sets a cookie when the upstream call throws", async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError("network down"));
    const response = await mintDemoSession(request(), { fetcher });

    expect(response.status).toBe(502);
    expect(getSetCookies(response)).toHaveLength(0);
  });
});
