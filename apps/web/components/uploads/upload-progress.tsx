"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";

import type { TaskStatus } from "../../lib/api/contracts";
import { orchestrationApi } from "../../lib/api/orchestration";
import type { UploadItem } from "../../lib/upload/upload-machine";
import { EvidenceChip, shortReference } from "../cases/evidence-chip";
import styles from "./upload-progress.module.css";

// Background processing status is a live, moving target after the completion
// response registers the document (PENDING -> RUNNING -> a terminal state) —
// it must never be shown as a single frozen snapshot. This mirrors the
// orchestration console's poll pattern (components/orchestration/
// orchestration-console.tsx): a bounded, ~4s recursive setTimeout that stops
// the moment a terminal status is observed, and never fabricates progress on
// a transient poll failure.
const POLL_INTERVAL_MS = 4000;
const MAX_POLL_CYCLES = 20;

const TERMINAL_TASK_STATUSES = new Set<TaskStatus>([
  "SUCCEEDED",
  "FAILED_MANUAL_REVIEW",
  "SUPERSEDED",
]);
const KNOWN_TASK_STATUSES = new Set<TaskStatus>([
  "PENDING",
  "RUNNING",
  "RETRY_WAIT",
  "SUCCEEDED",
  "FAILED_MANUAL_REVIEW",
  "SUPERSEDED",
]);

function asKnownTaskStatus(value: string): TaskStatus | null {
  return (KNOWN_TASK_STATUSES as ReadonlySet<string>).has(value) ? (value as TaskStatus) : null;
}

function isTerminal(status: TaskStatus | null): boolean {
  return status !== null && TERMINAL_TASK_STATUSES.has(status);
}

async function defaultGetTaskStatus(taskId: string): Promise<string> {
  return (await orchestrationApi.getTask(taskId)).status;
}

interface UploadProgressProps {
  item: UploadItem & { taskId?: string | null };
  onCancel: (id: string) => void;
  onRetry: (id: string) => void;
  // Injectable for tests; defaults to the real GET /api/v1/tasks/{taskId}
  // read (allowlisted in creditops-bff.ts) via the orchestration BFF client.
  getTaskStatus?: (taskId: string) => Promise<string>;
}

export function UploadProgress({
  item,
  onCancel,
  onRetry,
  getTaskStatus = defaultGetTaskStatus,
}: UploadProgressProps) {
  const cancellable = item.status === "REQUESTING_INTENT" || item.status === "UPLOADING";
  const [liveTaskStatus, setLiveTaskStatus] = useState<TaskStatus | null>(item.taskStatus);

  useEffect(() => {
    setLiveTaskStatus(item.taskStatus);
  }, [item.taskStatus]);

  const mountedRef = useRef(true);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const poll = useCallback(
    async (taskId: string, remaining: number) => {
      if (!mountedRef.current) return;
      let nextStatus: TaskStatus | null = null;
      try {
        const raw = await getTaskStatus(taskId);
        nextStatus = asKnownTaskStatus(raw);
      } catch {
        // Transient poll failure: keep showing the last known status and try
        // again on the next cycle rather than surfacing noise or faking
        // success.
      }
      if (!mountedRef.current) return;
      if (nextStatus !== null) setLiveTaskStatus(nextStatus);
      if (isTerminal(nextStatus)) return;
      if (remaining > 0) {
        timerRef.current = setTimeout(() => {
          void poll(taskId, remaining - 1);
        }, POLL_INTERVAL_MS);
      }
    },
    [getTaskStatus],
  );

  useEffect(() => {
    mountedRef.current = true;
    const taskId = item.taskId;
    if (
      item.status === "REGISTERED" &&
      taskId &&
      !isTerminal(item.taskStatus)
    ) {
      timerRef.current = setTimeout(() => {
        void poll(taskId, MAX_POLL_CYCLES - 1);
      }, POLL_INTERVAL_MS);
    }
    return () => {
      mountedRef.current = false;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
    // Only (re)starts polling when the item first becomes a registered task
    // with a fresh taskId; `poll` schedules its own subsequent cycles.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item.status, item.taskId]);

  const displayItem = { ...item, taskStatus: liveTaskStatus };

  return (
    <li className={styles.item}>
      <div className={styles.heading}>
        <div className={styles.meta}>
          <strong className={styles.name}>{item.file.name}</strong>
          <span className={styles.size}>{formatBytes(item.file.size)}</span>
        </div>
        {cancellable ? (
          <button
            aria-label={`Hủy tải ${item.file.name}`}
            className={styles.cancel}
            onClick={() => onCancel(item.id)}
            type="button"
          >
            Hủy
          </button>
        ) : null}
      </div>

      {item.status === "UPLOADING" ? (
        <div className={styles.track} aria-label={`Tiến độ ${item.file.name}`} aria-valuemax={100} aria-valuemin={0} aria-valuenow={item.progress} role="progressbar">
          <span className={styles.fill} style={{ width: `${item.progress}%` }} />
        </div>
      ) : null}

      <p aria-live="polite" className={`${styles.state} ${stateTone(displayItem)}`}>
        {statusText(displayItem)}
      </p>

      {item.status === "DUPLICATE" && item.duplicateOfDocumentId ? (
        <div className={styles.evidence}>
          <EvidenceChip
            label="Tài liệu đã có"
            reference={shortReference(item.duplicateOfDocumentId)}
            title={`Mã tài liệu: ${item.duplicateOfDocumentId}`}
          />
        </div>
      ) : null}

      {item.status === "FAILED" || item.status === "CANCELLED" ? (
        <button
          aria-label={`Thử lại ${item.file.name}`}
          className={`button button-secondary button-small ${styles.retry}`}
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

function stateTone(item: UploadItem): string {
  switch (item.status) {
    case "REQUESTING_INTENT":
    case "UPLOADING":
    case "VERIFYING":
      return styles.toneInfo;
    case "REGISTERED":
      return taskStatusTone(item.taskStatus);
    case "DUPLICATE":
      return styles.toneMuted;
    case "CANCELLED":
      return styles.toneMuted;
    case "FAILED":
      return styles.toneRisk;
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

function taskStatusTone(status: UploadItem["taskStatus"]): string {
  switch (status) {
    case "PENDING":
    case "RETRY_WAIT":
      return styles.toneAmber;
    case "RUNNING":
      return styles.toneInfo;
    case "SUCCEEDED":
      return styles.toneOk;
    case "FAILED_MANUAL_REVIEW":
      return styles.toneRisk;
    case "SUPERSEDED":
    case null:
      return styles.toneMuted;
  }
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
