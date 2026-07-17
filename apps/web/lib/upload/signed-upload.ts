import type { SignedUploadIntentDto } from "../api/contracts";

export interface DirectUploadOptions {
  signal: AbortSignal;
  onProgress: (percent: number) => void;
  xhrFactory?: () => XMLHttpRequest;
}

export function uploadSigned(
  intent: SignedUploadIntentDto,
  file: File,
  options: DirectUploadOptions,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = (options.xhrFactory ?? (() => new XMLHttpRequest()))();
    const abort = () => xhr.abort();
    const cleanUp = () => options.signal.removeEventListener("abort", abort);

    if (options.signal.aborted) {
      reject(abortError());
      return;
    }

    xhr.open(intent.method, intent.uploadUrl, true);
    for (const [name, value] of Object.entries(intent.headers)) {
      xhr.setRequestHeader(name, value);
    }
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        options.onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      cleanUp();
      if (xhr.status >= 200 && xhr.status < 300) {
        options.onProgress(100);
        resolve();
      } else {
        reject(new Error("SIGNED_UPLOAD_FAILED"));
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
    xhr.send(file);
  });
}

function abortError(): DOMException {
  return new DOMException("Upload cancelled", "AbortError");
}
