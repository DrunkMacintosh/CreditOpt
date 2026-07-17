import type {
  CompleteUploadResponseDto,
  CreateCaseRequestDto,
  CreateUploadIntentRequestDto,
  CreditCaseDto,
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
  if (error instanceof ApiClientError) {
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

export class CreditOpsApiClient implements CreditOpsApi {
  private readonly baseUrl: string;

  constructor(
    baseUrl = process.env.NEXT_PUBLIC_CREDITOPS_API_URL ?? "",
    private readonly fetcher: Fetcher = fetch,
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  async listCases(): Promise<CreditCaseDto[]> {
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
