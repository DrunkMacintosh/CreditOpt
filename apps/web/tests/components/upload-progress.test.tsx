import { act, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { UploadProgress } from "../../components/uploads/upload-progress";
import type { UploadItem } from "../../lib/upload/upload-machine";

function pdfFile() {
  return new File(["synthetic-pdf-content"], "ho-so.pdf", {
    type: "application/pdf",
  });
}

function registeredItem(
  overrides: Partial<UploadItem & { taskId: string | null }> = {},
): UploadItem & { taskId: string | null } {
  return {
    id: "item-1",
    file: pdfFile(),
    status: "REGISTERED",
    progress: 100,
    error: null,
    duplicateOfDocumentId: null,
    taskStatus: "PENDING",
    taskId: "task-1",
    ...overrides,
  };
}

describe("UploadProgress task-status polling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("advances from PENDING through RUNNING to SUCCEEDED instead of a frozen snapshot", async () => {
    const getTaskStatus = vi
      .fn()
      .mockResolvedValueOnce("RUNNING")
      .mockResolvedValueOnce("SUCCEEDED");

    render(
      <UploadProgress
        getTaskStatus={getTaskStatus}
        item={registeredItem()}
        onCancel={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText("Đang chờ xử lý")).toBeVisible();
    expect(getTaskStatus).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(screen.getByText("Đang xử lý tài liệu")).toBeVisible();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(screen.getByText("Đã xử lý xong")).toBeVisible();

    expect(getTaskStatus).toHaveBeenCalledTimes(2);
    expect(getTaskStatus).toHaveBeenNthCalledWith(1, "task-1");

    // Terminal: no further polling.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000);
    });
    expect(getTaskStatus).toHaveBeenCalledTimes(2);
  });

  it("surfaces a manual-review failure honestly, never as success", async () => {
    const getTaskStatus = vi.fn().mockResolvedValue("FAILED_MANUAL_REVIEW");

    render(
      <UploadProgress
        getTaskStatus={getTaskStatus}
        item={registeredItem({ taskStatus: "RUNNING" })}
        onCancel={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText("Đang xử lý tài liệu")).toBeVisible();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(screen.getByText("Cần rà soát thủ công")).toBeVisible();
    expect(screen.queryByText("Đã xử lý xong")).not.toBeInTheDocument();
  });

  it("does not poll once already in a terminal state", async () => {
    const getTaskStatus = vi.fn();
    render(
      <UploadProgress
        getTaskStatus={getTaskStatus}
        item={registeredItem({ taskStatus: "SUCCEEDED" })}
        onCancel={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(getTaskStatus).not.toHaveBeenCalled();
  });

  it("does not poll without a taskId", async () => {
    const getTaskStatus = vi.fn();
    render(
      <UploadProgress
        getTaskStatus={getTaskStatus}
        item={registeredItem({ taskId: null })}
        onCancel={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(getTaskStatus).not.toHaveBeenCalled();
  });

  it("keeps the last known status and keeps trying on a transient poll failure", async () => {
    const getTaskStatus = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("network blip"))
      .mockResolvedValueOnce("SUCCEEDED");

    render(
      <UploadProgress
        getTaskStatus={getTaskStatus}
        item={registeredItem()}
        onCancel={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(screen.getByText("Đang chờ xử lý")).toBeVisible();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(screen.getByText("Đã xử lý xong")).toBeVisible();
    expect(getTaskStatus).toHaveBeenCalledTimes(2);
  });

  it("stops polling on unmount", async () => {
    const getTaskStatus = vi.fn().mockResolvedValue("RUNNING");
    const { unmount } = render(
      <UploadProgress
        getTaskStatus={getTaskStatus}
        item={registeredItem()}
        onCancel={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(getTaskStatus).toHaveBeenCalledTimes(1);
    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000);
    });
    expect(getTaskStatus).toHaveBeenCalledTimes(1);
  });
});
