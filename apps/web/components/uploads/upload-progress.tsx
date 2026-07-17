import React from "react";

import type { UploadItem } from "../../lib/upload/upload-machine";

interface UploadProgressProps {
  item: UploadItem;
  onCancel: (id: string) => void;
  onRetry: (id: string) => void;
}

export function UploadProgress({ item, onCancel, onRetry }: UploadProgressProps) {
  const cancellable = item.status === "REQUESTING_INTENT" || item.status === "UPLOADING";
  return (
    <li className="upload-item">
      <div className="upload-item-heading">
        <div>
          <strong>{item.file.name}</strong>
          <span>{formatBytes(item.file.size)}</span>
        </div>
        {cancellable ? (
          <button
            aria-label={`Hủy tải ${item.file.name}`}
            className="text-button"
            onClick={() => onCancel(item.id)}
            type="button"
          >
            Hủy
          </button>
        ) : null}
      </div>

      {item.status === "UPLOADING" ? (
        <div className="progress-track" aria-label={`Tiến độ ${item.file.name}`} aria-valuemax={100} aria-valuemin={0} aria-valuenow={item.progress} role="progressbar">
          <span style={{ width: `${item.progress}%` }} />
        </div>
      ) : null}

      <p aria-live="polite" className={`upload-state upload-state-${item.status.toLowerCase()}`}>
        {statusText(item)}
      </p>
      {item.status === "FAILED" || item.status === "CANCELLED" ? (
        <button
          aria-label={`Thử lại ${item.file.name}`}
          className="button button-secondary button-small"
          onClick={() => onRetry(item.id)}
          type="button"
        >
          Thử lại
        </button>
      ) : null}
    </li>
  );
}

function statusText(item: UploadItem): string {
  switch (item.status) {
    case "REQUESTING_INTENT":
      return "Đang xin quyền tải lên";
    case "UPLOADING":
      return "Đang tải trực tiếp lên kho tài liệu";
    case "VERIFYING":
      return "Đang xác minh tài liệu. Không thể hủy ở bước này.";
    case "REGISTERED":
      return taskStatusText(item.taskStatus);
    case "DUPLICATE":
      return "Tài liệu trùng khớp với bản đã có";
    case "CANCELLED":
      return "Đã hủy tải lên";
    case "FAILED":
      return item.error ?? "Không thể tải tài liệu.";
  }
}

function taskStatusText(status: UploadItem["taskStatus"]): string {
  switch (status) {
    case "PENDING":
      return "Đang chờ xử lý";
    case "RUNNING":
      return "Đang xử lý tài liệu";
    case "RETRY_WAIT":
      return "Đang chờ thử lại";
    case "SUCCEEDED":
      return "Đã xử lý xong";
    case "FAILED_MANUAL_REVIEW":
      return "Cần rà soát thủ công";
    case "SUPERSEDED":
      return "Tác vụ đã được thay thế";
    case null:
      return "Trạng thái tác vụ không xác định";
  }
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
