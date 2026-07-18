export interface CaseCapabilities {
  canUpload: boolean;
  canConfirm: boolean;
  canCompleteIntake: boolean;
}

export interface CreditCaseDto {
  id: string;
  version: number;
  assignedOfficerId: string;
  requestedAmount: string | null;
  purpose: string | null;
  workflowState: string | null;
  updatedAt: string | null;
  capabilities: CaseCapabilities;
}

export interface CaseCollectionCapabilities {
  canCreateCase: boolean;
}

export interface CreditCaseListDto {
  items: CreditCaseDto[];
  nextCursor: string | null;
  capabilities: CaseCollectionCapabilities;
}

export interface CreateCaseRequestDto {
  requestedAmount: string;
  purpose: string;
}

export interface CreateUploadIntentRequestDto {
  fileName: string;
  contentType: string;
  sizeBytes: number;
}

interface UploadIntentBaseDto {
  intentId: string;
  expiresAt: string;
  uploadUrl: string;
  headers: Readonly<Record<string, string>>;
}

export interface SignedUploadIntentDto extends UploadIntentBaseDto {
  mode: "SIGNED";
  method: "POST" | "PUT";
}

export interface ResumableUploadIntentDto extends UploadIntentBaseDto {
  mode: "RESUMABLE";
}

export type UploadIntentDto = SignedUploadIntentDto | ResumableUploadIntentDto;

export type TaskStatus =
  | "PENDING"
  | "RUNNING"
  | "RETRY_WAIT"
  | "SUCCEEDED"
  | "FAILED_MANUAL_REVIEW"
  | "SUPERSEDED";

export interface TaskStatusDto {
  id: string;
  status: TaskStatus;
}

export interface DuplicateUploadResponseDto {
  outcome: "DUPLICATE";
  duplicateOfDocumentId: string;
}

export interface RegisteredUploadResponseDto {
  outcome: "REGISTERED";
  documentId: string;
  documentVersionId: string;
  task: TaskStatusDto;
}

export type CompleteUploadResponseDto =
  | DuplicateUploadResponseDto
  | RegisteredUploadResponseDto;

export interface ApiErrorDto {
  code: string;
  messageVi: string;
  correlationId: string | null;
  retryable: boolean;
}

export interface CaseApi {
  listCases(): Promise<CreditCaseListDto>;
  getCase(caseId: string): Promise<CreditCaseDto>;
  createCase(request: CreateCaseRequestDto): Promise<CreditCaseDto>;
}

export interface UploadApi {
  createUploadIntent(
    caseId: string,
    request: CreateUploadIntentRequestDto,
  ): Promise<UploadIntentDto>;
  completeUploadIntent(
    intentId: string,
    idempotencyKey: string,
  ): Promise<CompleteUploadResponseDto>;
}

export type CreditOpsApi = CaseApi & UploadApi;
