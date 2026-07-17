import { describe, expect, it, vi } from "vitest";

import { CreditOpsApiClient } from "../../lib/api/client";
import {
  CSRF_COOKIE_NAME,
  CSRF_HEADER_NAME,
  SESSION_COOKIE_NAME,
  proxyCreditOpsRequest,
} from "../../lib/server/creditops-bff";

const upstreamBaseUrl = "https://creditops-api.invalid";

function request(
  path: string,
  init: RequestInit = {},
  cookies = `${SESSION_COOKIE_NAME}=workforce-token`,
) {
  const headers = new Headers(init.headers);
  if (cookies) headers.set("cookie", cookies);
  return new Request(`https://app.invalid/api/creditops${path}`, {
    ...init,
    headers,
  });
}

describe("CreditOps JSON BFF", () => {
  it("forwards an allowlisted request with server-side bearer auth and strips sensitive response headers", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: {
          "content-type": "application/json",
          "set-cookie": "leaked=secret",
          authorization: "Bearer leaked",
          server: "private-upstream",
          "x-request-id": "request-1",
        },
      }),
    );

    const response = await proxyCreditOpsRequest(
      request("/api/v1/cases"),
      ["api", "v1", "cases"],
      { fetcher, upstreamBaseUrl },
    );

    expect(response.status).toBe(200);
    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe("https://creditops-api.invalid/api/v1/cases");
    expect(new Headers(init.headers).get("authorization")).toBe(
      "Bearer workforce-token",
    );
    expect(new Headers(init.headers).has("cookie")).toBe(false);
    expect(response.headers.get("x-request-id")).toBe("request-1");
    expect(response.headers.has("set-cookie")).toBe(false);
    expect(response.headers.has("authorization")).toBe(false);
    expect(response.headers.has("server")).toBe(false);
  });

  it("fails closed without a server-side session token", async () => {
    const fetcher = vi.fn();
    const response = await proxyCreditOpsRequest(
      request("/api/v1/cases", {}, ""),
      ["api", "v1", "cases"],
      { fetcher, upstreamBaseUrl },
    );

    expect(response.status).toBe(401);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([
    ["GET", "/api/v1/documents/document-1", ["api", "v1", "documents", "document-1"]],
    ["DELETE", "/api/v1/cases/case-1", ["api", "v1", "cases", "case-1"]],
  ])("rejects non-allowlisted %s paths", async (method, path, segments) => {
    const fetcher = vi.fn();
    const response = await proxyCreditOpsRequest(
      request(path, { method }),
      segments,
      { fetcher, upstreamBaseUrl },
    );

    expect(response.status).toBe(404);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each(["multipart/form-data; boundary=secret", "application/octet-stream", "application/pdf"])(
    "rejects direct document body type %s",
    async (contentType) => {
      const fetcher = vi.fn();
      const cookies = `${SESSION_COOKIE_NAME}=workforce-token; ${CSRF_COOKIE_NAME}=csrf-value`;
      const response = await proxyCreditOpsRequest(
        request(
          "/api/v1/cases",
          {
            method: "POST",
            headers: {
              "content-type": contentType,
              origin: "https://app.invalid",
              [CSRF_HEADER_NAME]: "csrf-value",
            },
            body: "document bytes",
          },
          cookies,
        ),
        ["api", "v1", "cases"],
        { fetcher, upstreamBaseUrl },
      );

      expect(response.status).toBe(415);
      expect(fetcher).not.toHaveBeenCalled();
    },
  );

  it.each([
    [undefined, "csrf-value"],
    ["https://evil.invalid", "csrf-value"],
    ["https://app.invalid", undefined],
    ["https://app.invalid", "different-value"],
  ])("fails closed for invalid mutation origin/token %#", async (origin, headerToken) => {
    const fetcher = vi.fn();
    const headers = new Headers({ "content-type": "application/json" });
    if (origin) headers.set("origin", origin);
    if (headerToken) headers.set(CSRF_HEADER_NAME, headerToken);
    const response = await proxyCreditOpsRequest(
      request(
        "/api/v1/cases",
        { method: "POST", headers, body: "{}" },
        `${SESSION_COOKIE_NAME}=workforce-token; ${CSRF_COOKIE_NAME}=csrf-value`,
      ),
      ["api", "v1", "cases"],
      { fetcher, upstreamBaseUrl },
    );

    expect(response.status).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("forwards only JSON mutations with a matching double-submit token", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      Response.json({ id: "case-1" }, { status: 201 }),
    );
    const response = await proxyCreditOpsRequest(
      request(
        "/api/v1/upload-intents/intent-1/complete",
        {
          method: "POST",
          headers: {
            "content-type": "application/json",
            origin: "https://app.invalid",
            [CSRF_HEADER_NAME]: "csrf-value",
            "idempotency-key": "stable-key",
          },
          body: "{}",
        },
        `${SESSION_COOKIE_NAME}=workforce-token; ${CSRF_COOKIE_NAME}=csrf-value`,
      ),
      ["api", "v1", "upload-intents", "intent-1", "complete"],
      { fetcher, upstreamBaseUrl },
    );

    expect(response.status).toBe(201);
    const init = fetcher.mock.calls[0][1];
    const forwardedHeaders = new Headers(init.headers);
    expect(forwardedHeaders.get("idempotency-key")).toBe("stable-key");
    expect(forwardedHeaders.has(CSRF_HEADER_NAME)).toBe(false);
    expect(init.body).toBe("{}");
  });

  it("fails closed when upload completion has no idempotency key", async () => {
    const fetcher = vi.fn();
    const response = await proxyCreditOpsRequest(
      request(
        "/api/v1/upload-intents/intent-1/complete",
        {
          method: "POST",
          headers: {
            "content-type": "application/json",
            origin: "https://app.invalid",
            [CSRF_HEADER_NAME]: "csrf-value",
          },
          body: "{}",
        },
        `${SESSION_COOKIE_NAME}=workforce-token; ${CSRF_COOKIE_NAME}=csrf-value`,
      ),
      ["api", "v1", "upload-intents", "intent-1", "complete"],
      { fetcher, upstreamBaseUrl },
    );

    expect(response.status).toBe(400);
    expect(fetcher).not.toHaveBeenCalled();
  });
});

describe("browser CreditOps client", () => {
  it("uses the same-origin BFF and adds the non-secret CSRF token to mutations", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({
          items: [],
          nextCursor: null,
          capabilities: { canCreateCase: false },
        }),
      )
      .mockResolvedValueOnce(
        Response.json({
          id: "case-1",
          version: 1,
          assignedOfficerId: "officer-1",
          requestedAmount: "1",
          purpose: "Tổng hợp",
          capabilities: {
            canUpload: false,
            canConfirm: false,
            canCompleteIntake: false,
          },
        }),
      );
    const client = new CreditOpsApiClient(undefined, fetcher, () => "csrf-value");

    await client.listCases();
    await client.createCase({ requestedAmount: "1", purpose: "Tổng hợp" });

    expect(fetcher.mock.calls[0][0]).toBe("/api/creditops/api/v1/cases");
    expect(fetcher.mock.calls[1][0]).toBe("/api/creditops/api/v1/cases");
    expect(new Headers(fetcher.mock.calls[1][1].headers).get(CSRF_HEADER_NAME)).toBe(
      "csrf-value",
    );
  });
});
