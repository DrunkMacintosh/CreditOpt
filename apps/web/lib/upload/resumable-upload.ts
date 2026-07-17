import type { ResumableUploadIntentDto } from "../api/contracts";
import type { DirectUploadOptions } from "./signed-upload";

const TUS_VERSION = "1.0.0";
const CHUNK_SIZE = 6 * 1024 * 1024;

interface TusResponse {
  getHeader(name: string): string | null;
}

export async function uploadResumable(
  intent: ResumableUploadIntentDto,
  file: File,
  options: DirectUploadOptions,
): Promise<void> {
  const uploadLocation = await createTusUpload(intent, file, options);
  let offset = 0;

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
    const nextOffset = Number(response.getHeader("Upload-Offset"));
    offset = Number.isFinite(nextOffset) && nextOffset > chunkStart
      ? nextOffset
      : chunkStart + chunk.size;
  }

  options.onProgress(100);
}

async function createTusUpload(
  intent: ResumableUploadIntentDto,
  file: File,
  options: DirectUploadOptions,
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
  if (!location) throw new Error("TUS_LOCATION_MISSING");
  return new URL(location, intent.uploadUrl).toString();
}

function hasHeader(headers: Readonly<Record<string, string>>, name: string): boolean {
  const normalizedName = name.toLowerCase();
  return Object.keys(headers).some((header) => header.toLowerCase() === normalizedName);
}

function xhrRequest(
  method: "POST" | "PATCH",
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
        reject(new Error("TUS_UPLOAD_FAILED"));
      }
    };
    xhr.onerror = () => {
      cleanUp();
      reject(new Error("DIRECT_UPLOAD_NETWORK_ERROR"));
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
