import type {
  CompleteUploadResponseDto,
  CreateCaseRequestDto,
  CreateUploadIntentRequestDto,
  CreditCaseDto,
  CreditCaseListDto,
  CreditOpsApi,
  UploadIntentDto,
} from "./contracts";
import {
  parseApiError,
  parseCompleteUpload,
  parseCreditCase,
  parseCreditCaseList,
  parseUploadIntent,
} from "./schemas";

type Fetcher = typeof fetch;
type CsrfTokenProvider = () => string | null;

const BFF_BASE_URL = "/api/creditops";
const CSRF_COOKIE_NAME = "__Host-creditops-csrf";
const CSRF_HEADER_NAME = "x-creditops-csrf";

export class ApiClientError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly retryable: boolean,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

export function getVietnameseApiError(error: unknown): string {
  if (error instanceof ApiClientError || isDirectStorageError(error)) {
    if (error.code === "UPLOAD_INTENT_EXPIRED") {
      return "Phiên tải lên đã hết hạn. Vui lòng thử lại.";
    }
    switch (error.status) {
      case 401:
        return "Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại.";
      case 403:
        return "Bạn không có quyền thực hiện thao tác này trên hồ sơ.";
      case 409:
        return "Dữ liệu đã thay đổi hoặc thao tác bị trùng. Vui lòng tải lại.";
      case 413:
        return "Tài liệu vượt quá dung lượng được phép.";
      case 415:
        return "Định dạng tài liệu chưa được hỗ trợ.";
      case 422:
        return "Thông tin tài liệu chưa hợp lệ. Vui lòng kiểm tra và thử lại.";
    }
  }
  return "Không thể hoàn tất yêu cầu. Vui lòng thử lại.";
}

function isDirectStorageError(
  error: unknown,
): error is { readonly name: "DirectStorageError"; readonly status: number; readonly code?: string } {
  return (
    error instanceof Error &&
    error.name === "DirectStorageError" &&
    typeof (error as { status?: unknown }).status === "number"
  );
}

export class CreditOpsApiClient implements CreditOpsApi {
  private readonly baseUrl: string;

  constructor(
    baseUrl = BFF_BASE_URL,
    private readonly fetcher: Fetcher = fetch,
    private readonly csrfTokenProvider: CsrfTokenProvider = readBrowserCsrfToken,
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  async listCases(): Promise<CreditCaseListDto> {
    return parseCreditCaseList(await this.request("/api/v1/cases"));
  }

  async getCase(caseId: string): Promise<CreditCaseDto> {
    return parseCreditCase(
      await this.request(`/api/v1/cases/${encodeURIComponent(caseId)}`),
    );
  }

  async createCase(request: CreateCaseRequestDto): Promise<CreditCaseDto> {
    return parseCreditCase(
      await this.request("/api/v1/cases", {
        method: "POST",
        body: JSON.stringify(request),
      }),
    );
  }

  async createUploadIntent(
    caseId: string,
    request: CreateUploadIntentRequestDto,
  ): Promise<UploadIntentDto> {
    return parseUploadIntent(
      await this.request(
        `/api/v1/cases/${encodeURIComponent(caseId)}/upload-intents`,
        { method: "POST", body: JSON.stringify(request) },
      ),
    );
  }

  async completeUploadIntent(
    intentId: string,
    idempotencyKey: string,
  ): Promise<CompleteUploadResponseDto> {
    return parseCompleteUpload(
      await this.request(
        `/api/v1/upload-intents/${encodeURIComponent(intentId)}/complete`,
        {
          method: "POST",
          headers: { "Idempotency-Key": idempotencyKey },
          body: "{}",
        },
      ),
    );
  }

  private async request(path: string, init: RequestInit = {}): Promise<unknown> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body !== undefined) headers.set("Content-Type", "application/json");
    if (isMutation(init.method)) {
      const csrfToken = this.csrfTokenProvider();
      if (csrfToken) headers.set(CSRF_HEADER_NAME, csrfToken);
    }

    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      ...init,
      headers,
      credentials: "include",
      cache: "no-store",
    });
    const body = await parseJson(response);
    if (!response.ok) {
      const apiError = parseApiError(body);
      throw new ApiClientError(
        response.status,
        apiError?.code ?? "REQUEST_FAILED",
        apiError?.messageVi || "Yêu cầu không thành công.",
        apiError?.retryable ?? response.status >= 500,
      );
    }
    return body;
  }
}

function isMutation(method: string | undefined): boolean {
  return method !== undefined && !["GET", "HEAD"].includes(method.toUpperCase());
}

function readBrowserCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  for (const part of document.cookie.split(";")) {
    const index = part.indexOf("=");
    if (index < 0 || part.slice(0, index).trim() !== CSRF_COOKIE_NAME) continue;
    try {
      return decodeURIComponent(part.slice(index + 1).trim());
    } catch {
      return null;
    }
  }
  return null;
}

async function parseJson(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export const creditOpsApi = new CreditOpsApiClient();
