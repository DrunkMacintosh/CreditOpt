import type {
  ApiErrorDto,
  CaseCapabilities,
  CompleteUploadResponseDto,
  CreditCaseDto,
  TaskStatus,
  TaskStatusDto,
  UploadIntentDto,
} from "./contracts";

const TASK_STATUSES = new Set<TaskStatus>([
  "PENDING",
  "RUNNING",
  "RETRY_WAIT",
  "SUCCEEDED",
  "FAILED_MANUAL_REVIEW",
  "SUPERSEDED",
]);

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`Phản hồi ${label} không đúng định dạng.`);
  }
  return value as Record<string, unknown>;
}

function string(value: unknown, label: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`Phản hồi thiếu ${label}.`);
  }
  return value;
}

function nullableString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function positiveInteger(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 1) {
    throw new Error(`Phản hồi thiếu ${label} hợp lệ.`);
  }
  return value;
}

function parseHeaders(value: unknown): Readonly<Record<string, string>> {
  if (value === undefined || value === null) return {};
  const raw = record(value, "headers");
  const headers: Record<string, string> = {};
  for (const [name, headerValue] of Object.entries(raw)) {
    if (typeof headerValue !== "string") {
      throw new Error("Phản hồi headers không đúng định dạng.");
    }
    headers[name] = headerValue;
  }
  return headers;
}

function parseCapabilities(value: unknown): CaseCapabilities {
  const raw = record(value, "capabilities");
  return {
    canUpload: raw.canUpload === true,
    canConfirm: raw.canConfirm === true,
    canCompleteIntake: raw.canCompleteIntake === true,
  };
}

export function parseCreditCase(value: unknown): CreditCaseDto {
  const raw = record(value, "hồ sơ");
  const financingRequest =
    typeof raw.financingRequest === "object" && raw.financingRequest !== null
      ? record(raw.financingRequest, "yêu cầu cấp vốn")
      : {};

  return {
    id: string(raw.id, "id hồ sơ"),
    version: positiveInteger(raw.version ?? raw.caseVersion, "phiên bản hồ sơ"),
    assignedOfficerId: string(raw.assignedOfficerId, "cán bộ phụ trách"),
    requestedAmount: nullableString(
      raw.requestedAmount ?? financingRequest.requestedAmount,
    ),
    purpose: nullableString(raw.purpose ?? financingRequest.purpose),
    workflowState: nullableString(raw.workflowState),
    updatedAt: nullableString(raw.updatedAt),
    capabilities: parseCapabilities(raw.capabilities),
  };
}

export function parseCreditCaseList(value: unknown): CreditCaseDto[] {
  const items = Array.isArray(value)
    ? value
    : record(value, "danh sách hồ sơ").items;
  if (!Array.isArray(items)) {
    throw new Error("Phản hồi danh sách hồ sơ không đúng định dạng.");
  }
  return items.map(parseCreditCase);
}

export function parseUploadIntent(value: unknown): UploadIntentDto {
  const raw = record(value, "phiên tải lên");
  const authorization =
    typeof raw.authorization === "object" && raw.authorization !== null
      ? record(raw.authorization, "ủy quyền tải lên")
      : {};
  const normalizedMode = string(raw.mode, "chế độ tải lên").toUpperCase();
  const common = {
    intentId: string(raw.intentId ?? raw.id, "id phiên tải lên"),
    expiresAt: string(raw.expiresAt, "thời điểm hết hạn"),
    uploadUrl: string(
      raw.uploadUrl ?? raw.tusEndpoint ?? authorization.url,
      "địa chỉ tải lên",
    ),
    headers: parseHeaders(raw.headers ?? authorization.headers),
  };

  if (normalizedMode === "SIGNED") {
    const method = String(raw.method ?? authorization.method ?? "PUT").toUpperCase();
    if (method !== "POST" && method !== "PUT") {
      throw new Error("Phương thức tải lên không được hỗ trợ.");
    }
    return { ...common, mode: "SIGNED", method };
  }
  if (normalizedMode === "RESUMABLE") {
    return { ...common, mode: "RESUMABLE" };
  }
  throw new Error("Chế độ tải lên không được hỗ trợ.");
}

export function parseTaskStatus(value: unknown): TaskStatusDto {
  const raw = record(value, "trạng thái tác vụ");
  const status = string(raw.status, "trạng thái") as TaskStatus;
  if (!TASK_STATUSES.has(status)) {
    throw new Error("Trạng thái tác vụ không được hỗ trợ.");
  }
  return { id: string(raw.id, "id tác vụ"), status };
}

export function parseCompleteUpload(value: unknown): CompleteUploadResponseDto {
  const raw = record(value, "hoàn tất tải lên");
  return {
    documentId: nullableString(raw.documentId),
    documentVersionId: nullableString(raw.documentVersionId),
    duplicateOfDocumentId: nullableString(raw.duplicateOfDocumentId),
    task: raw.task === null || raw.task === undefined ? null : parseTaskStatus(raw.task),
  };
}

export function parseApiError(value: unknown): ApiErrorDto | null {
  try {
    const raw = record(value, "lỗi");
    return {
      code: string(raw.code, "mã lỗi"),
      messageVi: typeof raw.messageVi === "string" ? raw.messageVi : "",
      correlationId: nullableString(raw.correlationId),
      retryable: raw.retryable === true,
    };
  } catch {
    return null;
  }
}
