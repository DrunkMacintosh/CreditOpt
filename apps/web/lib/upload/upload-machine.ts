import type {
  ResumableUploadIntentDto,
  SignedUploadIntentDto,
  UploadIntentDto,
} from "../api/contracts";
import { uploadResumable } from "./resumable-upload";
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
    options: DirectUploadOptions,
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
  options: DirectUploadOptions,
): Promise<void> {
  return intent.mode === "SIGNED"
    ? transport.uploadSigned(intent, file, options)
    : transport.uploadResumable(intent, file, options);
}
