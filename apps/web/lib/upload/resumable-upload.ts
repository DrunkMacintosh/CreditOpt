import type { ResumableUploadIntentDto } from "../api/contracts";
import { DirectStorageError, type DirectUploadOptions } from "./signed-upload";

const TUS_VERSION = "1.0.0";
const CHUNK_SIZE = 6 * 1024 * 1024;

interface TusResponse {
  getHeader(name: string): string | null;
}

export interface ResumableUploadOptions extends DirectUploadOptions {
  resumeUrl?: string;
  onResumeUrl?: (uploadUrl: string) => void;
}

export async function uploadResumable(
  intent: ResumableUploadIntentDto,
  file: File,
  options: ResumableUploadOptions,
): Promise<void> {
  const uploadLocation = options.resumeUrl
    ? validateUploadLocation(options.resumeUrl, intent.uploadUrl)
    : await createTusUpload(intent, file, options);
  let offset = options.resumeUrl
    ? await recoverTusOffset(intent, uploadLocation, file.size, options)
    : 0;

  if (file.size > 0) {
    options.onProgress(Math.round((offset / file.size) * 100));
  }

  while (offset < file.size) {
    if (options.signal.aborted) throw abortError();
    const chunk = file.slice(offset, Math.min(offset + CHUNK_SIZE, file.size));
    const chunkStart = offset;
    const response = await xhrRequest(
      "PATCH",
      uploadLocation,
      {
        ...intent.headers,
        "Tus-Resumable": TUS_VERSION,
        "Upload-Offset": String(offset),
        "Content-Type": "application/offset+octet-stream",
      },
      chunk,
      options,
      (loaded) => {
        const uploaded = Math.min(chunkStart + loaded, file.size);
        options.onProgress(
          file.size === 0 ? 100 : Math.round((uploaded / file.size) * 100),
        );
      },
    );
    offset = parseTusOffset(
      response.getHeader("Upload-Offset"),
      chunkStart,
      Math.min(chunkStart + chunk.size, file.size),
      false,
    );
  }

  options.onProgress(100);
}

async function createTusUpload(
  intent: ResumableUploadIntentDto,
  file: File,
  options: ResumableUploadOptions,
): Promise<string> {
  const headers: Record<string, string> = {
    ...intent.headers,
    "Tus-Resumable": TUS_VERSION,
    "Upload-Length": String(file.size),
  };
  if (!hasHeader(headers, "Upload-Metadata")) {
    headers["Upload-Metadata"] =
      `filename ${encodeBase64(file.name)},filetype ${encodeBase64(file.type || "application/octet-stream")}`;
  }
  const response = await xhrRequest(
    "POST",
    intent.uploadUrl,
    headers,
    null,
    options,
  );
  const location = response.getHeader("Location");
  if (!location) throw new DirectStorageError(0, "TUS_LOCATION_MISSING");
  const uploadLocation = validateUploadLocation(location, intent.uploadUrl);
  options.onResumeUrl?.(uploadLocation);
  return uploadLocation;
}

async function recoverTusOffset(
  intent: ResumableUploadIntentDto,
  uploadLocation: string,
  fileSize: number,
  options: ResumableUploadOptions,
): Promise<number> {
  const response = await xhrRequest(
    "HEAD",
    uploadLocation,
    { ...intent.headers, "Tus-Resumable": TUS_VERSION },
    null,
    options,
  );
  return parseTusOffset(response.getHeader("Upload-Offset"), 0, fileSize, true);
}

function parseTusOffset(
  rawOffset: string | null,
  minimum: number,
  maximum: number,
  allowMinimum: boolean,
): number {
  if (rawOffset === null || !/^\d+$/.test(rawOffset)) {
    throw new DirectStorageError(0, "TUS_OFFSET_INVALID");
  }
  const offset = Number(rawOffset);
  const monotonic = allowMinimum ? offset >= minimum : offset > minimum;
  if (!Number.isSafeInteger(offset) || !monotonic || offset > maximum) {
    throw new DirectStorageError(0, "TUS_OFFSET_INVALID");
  }
  return offset;
}

function validateUploadLocation(location: string, endpoint: string): string {
  const resolved = new URL(location, endpoint);
  if (resolved.origin !== new URL(endpoint).origin) {
    throw new DirectStorageError(0, "TUS_LOCATION_INVALID");
  }
  return resolved.toString();
}

function hasHeader(headers: Readonly<Record<string, string>>, name: string): boolean {
  const normalizedName = name.toLowerCase();
  return Object.keys(headers).some((header) => header.toLowerCase() === normalizedName);
}

function xhrRequest(
  method: "HEAD" | "POST" | "PATCH",
  url: string,
  headers: Readonly<Record<string, string>>,
  body: XMLHttpRequestBodyInit | null,
  options: DirectUploadOptions,
  onUploadProgress?: (loaded: number) => void,
): Promise<TusResponse> {
  return new Promise((resolve, reject) => {
    const xhr = (options.xhrFactory ?? (() => new XMLHttpRequest()))();
    const abort = () => xhr.abort();
    const cleanUp = () => options.signal.removeEventListener("abort", abort);

    if (options.signal.aborted) {
      reject(abortError());
      return;
    }

    xhr.open(method, url, true);
    for (const [name, value] of Object.entries(headers)) {
      xhr.setRequestHeader(name, value);
    }
    xhr.upload.onprogress = (event) => onUploadProgress?.(event.loaded);
    xhr.onload = () => {
      cleanUp();
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve({ getHeader: (name) => xhr.getResponseHeader(name) });
      } else {
        reject(new DirectStorageError(xhr.status));
      }
    };
    xhr.onerror = () => {
      cleanUp();
      reject(new DirectStorageError(0, "DIRECT_STORAGE_NETWORK_ERROR"));
    };
    xhr.onabort = () => {
      cleanUp();
      reject(abortError());
    };
    options.signal.addEventListener("abort", abort, { once: true });
    xhr.send(body);
  });
}

function encodeBase64(value: string): string {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function abortError(): DOMException {
  return new DOMException("Upload cancelled", "AbortError");
}
