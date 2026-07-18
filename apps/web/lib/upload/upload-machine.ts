import type {
  ResumableUploadIntentDto,
  SignedUploadIntentDto,
  TaskStatus,
  UploadIntentDto,
} from "../api/contracts";
import { uploadResumable, type ResumableUploadOptions } from "./resumable-upload";
import { uploadSigned, type DirectUploadOptions } from "./signed-upload";

export type UploadStatus =
  | "REQUESTING_INTENT"
  | "UPLOADING"
  | "VERIFYING"
  | "REGISTERED"
  | "DUPLICATE"
  | "FAILED"
  | "CANCELLED";

export interface UploadItem {
  id: string;
  file: File;
  status: UploadStatus;
  progress: number;
  error: string | null;
  duplicateOfDocumentId: string | null;
  taskStatus: TaskStatus | null;
}

export interface DirectUploadTransport {
  uploadSigned(
    intent: SignedUploadIntentDto,
    file: File,
    options: DirectUploadOptions,
  ): Promise<void>;
  uploadResumable(
    intent: ResumableUploadIntentDto,
    file: File,
    options: ResumableUploadOptions,
  ): Promise<void>;
}

export const directUploadTransport: DirectUploadTransport = {
  uploadSigned,
  uploadResumable,
};

export function uploadFromIntent(
  transport: DirectUploadTransport,
  intent: UploadIntentDto,
  file: File,
  options: ResumableUploadOptions,
): Promise<void> {
  return intent.mode === "SIGNED"
    ? transport.uploadSigned(intent, file, options)
    : transport.uploadResumable(intent, file, options);
}
