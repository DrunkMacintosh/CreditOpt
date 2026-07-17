"use client";

import React, { type ChangeEvent, useRef, useState } from "react";

import { creditOpsApi, getVietnameseApiError } from "../../lib/api/client";
import {
  directUploadTransport,
  type DirectUploadTransport,
  type UploadItem,
  uploadFromIntent,
} from "../../lib/upload/upload-machine";
import { UploadProgress } from "./upload-progress";

const ACCEPTED_CONTENT = new Map([
  [".pdf", "application/pdf"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
  [".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
]);

interface UploadZoneProps {
  caseId: string;
  canUpload?: boolean;
  api?: Pick<typeof creditOpsApi, "createUploadIntent" | "completeUploadIntent">;
  transport?: DirectUploadTransport;
}

export function UploadZone({
  caseId,
  canUpload = true,
  api = creditOpsApi,
  transport = directUploadTransport,
}: UploadZoneProps) {
  const [items, setItems] = useState<UploadItem[]>([]);
  const controllers = useRef(new Map<string, AbortController>());
  const sequence = useRef(0);

  function update(id: string, patch: Partial<UploadItem>) {
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    );
  }

  function selectFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    const nextItems = files.map((file) => {
      const id = `${Date.now()}-${sequence.current++}`;
      const validationError = validateFile(file);
      return {
        id,
        file,
        status: validationError ? "FAILED" : "REQUESTING_INTENT",
        progress: 0,
        error: validationError,
        duplicateOfDocumentId: null,
      } satisfies UploadItem;
    });
    setItems((current) => [...current, ...nextItems]);
    for (const item of nextItems) {
      if (!item.error) void processFile(item.id, item.file);
    }
    event.target.value = "";
  }

  async function processFile(id: string, file: File) {
    const controller = new AbortController();
    controllers.current.set(id, controller);
    update(id, {
      status: "REQUESTING_INTENT",
      progress: 0,
      error: null,
      duplicateOfDocumentId: null,
    });

    try {
      const contentType = contentTypeFor(file);
      const intent = await api.createUploadIntent(caseId, {
        fileName: file.name,
        contentType,
        sizeBytes: file.size,
      });
      if (!validFutureDate(intent.expiresAt)) {
        throw new ExpiredUploadError();
      }
      if (controller.signal.aborted) throw new DOMException("Cancelled", "AbortError");
      update(id, { status: "UPLOADING", progress: 0 });
      await uploadFromIntent(transport, intent, file, {
        signal: controller.signal,
        onProgress: (progress) => update(id, { progress }),
      });
      if (controller.signal.aborted) throw new DOMException("Cancelled", "AbortError");
      update(id, { status: "VERIFYING", progress: 100 });
      const result = await api.completeUploadIntent(intent.intentId, randomIdempotencyKey());
      if (
        !result.duplicateOfDocumentId &&
        (!result.documentId || !result.documentVersionId || !result.task)
      ) {
        throw new Error("UPLOAD_COMPLETION_INCOMPLETE");
      }
      update(id, result.duplicateOfDocumentId
        ? {
            status: "DUPLICATE",
            duplicateOfDocumentId: result.duplicateOfDocumentId,
          }
        : { status: "REGISTERED" });
    } catch (error) {
      if (controller.signal.aborted || isAbortError(error)) {
        update(id, { status: "CANCELLED", error: null });
      } else if (error instanceof ExpiredUploadError) {
        update(id, {
          status: "FAILED",
          error: "Phiên tải lên đã hết hạn. Vui lòng thử lại.",
        });
      } else {
        update(id, { status: "FAILED", error: getVietnameseApiError(error) });
      }
    } finally {
      controllers.current.delete(id);
    }
  }

  function cancel(id: string) {
    controllers.current.get(id)?.abort();
    update(id, { status: "CANCELLED", error: null });
  }

  function retry(id: string) {
    const item = items.find((candidate) => candidate.id === id);
    if (item) void processFile(item.id, item.file);
  }

  if (!canUpload) {
    return (
      <div className="state-panel" role="alert">
        <h2>Không thể tải tài liệu</h2>
        <p>Bạn không có quyền tải tài liệu cho hồ sơ này.</p>
      </div>
    );
  }

  return (
    <section aria-labelledby="upload-title" className="upload-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Tải trực tiếp có kiểm soát</p>
          <h2 id="upload-title">Thêm tài liệu vào hồ sơ</h2>
        </div>
        <span className="private-badge">Kho riêng tư</span>
      </div>
      <p className="section-copy">
        Trình duyệt gửi tệp thẳng tới kho tài liệu bằng quyền tải lên ngắn hạn. Hệ thống chỉ đăng ký tài liệu sau khi backend xác minh đối tượng đã lưu.
      </p>
      <div className="upload-dropzone">
        <input
          accept={Array.from(ACCEPTED_CONTENT.keys()).join(",")}
          id="document-files"
          multiple
          onChange={selectFiles}
          type="file"
        />
        <label className="button button-primary" htmlFor="document-files">
          Chọn tài liệu
        </label>
        <span>PDF, PNG, JPEG, DOCX hoặc XLSX</span>
      </div>
      {items.length > 0 ? (
        <ul aria-label="Tiến độ tải tài liệu" className="upload-list">
          {items.map((item) => (
            <UploadProgress
              item={item}
              key={item.id}
              onCancel={cancel}
              onRetry={retry}
            />
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function validateFile(file: File): string | null {
  const extension = extensionOf(file.name);
  const expectedType = ACCEPTED_CONTENT.get(extension);
  if (!expectedType || (file.type && file.type !== expectedType)) {
    return "Định dạng tài liệu chưa được hỗ trợ.";
  }
  return null;
}

function contentTypeFor(file: File): string {
  return file.type || ACCEPTED_CONTENT.get(extensionOf(file.name)) || "application/octet-stream";
}

function extensionOf(name: string): string {
  const index = name.lastIndexOf(".");
  return index < 0 ? "" : name.slice(index).toLowerCase();
}

function validFutureDate(value: string): boolean {
  const expiresAt = new Date(value).getTime();
  return Number.isFinite(expiresAt) && expiresAt > Date.now();
}

function randomIdempotencyKey(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

class ExpiredUploadError extends Error {}
