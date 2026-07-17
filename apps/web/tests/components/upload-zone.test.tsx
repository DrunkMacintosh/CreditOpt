import { act, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { ApiClientError, getVietnameseApiError } from "../../lib/api/client";
import type {
  CompleteUploadResponseDto,
  UploadIntentDto,
} from "../../lib/api/contracts";
import type { DirectUploadTransport } from "../../lib/upload/upload-machine";
import { uploadResumable } from "../../lib/upload/resumable-upload";
import type { ResumableUploadOptions } from "../../lib/upload/resumable-upload";
import { DirectStorageError, uploadSigned } from "../../lib/upload/signed-upload";
import { UploadZone } from "../../components/uploads/upload-zone";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function pdfFile() {
  return new File(["synthetic-pdf-content"], "ho-so-tong-hop.pdf", {
    type: "application/pdf",
  });
}

const signedIntent: UploadIntentDto = {
  mode: "SIGNED",
  intentId: "intent-1",
  expiresAt: "2099-07-17T08:00:00Z",
  uploadUrl: "https://storage.invalid/signed-object",
  method: "PUT",
  headers: { "x-upload-token": "ephemeral-value" },
};

const resumableIntent: UploadIntentDto = {
  mode: "RESUMABLE",
  intentId: "intent-2",
  expiresAt: "2099-07-17T08:00:00Z",
  uploadUrl: "https://storage.invalid/tus",
  headers: {
    authorization: "ephemeral-value",
    "Upload-Metadata": "bucketName cHJpdmF0ZQ==,objectName b3BhcXVl",
  },
};

const completed: CompleteUploadResponseDto = {
  outcome: "REGISTERED",
  documentId: "document-1",
  documentVersionId: "version-1",
  task: { id: "task-1", status: "PENDING" },
};

describe("UploadZone", () => {
  it("uploads directly and registers only after backend verification", async () => {
    const upload = deferred<void>();
    const completion = deferred<CompleteUploadResponseDto>();
    const api = {
      createUploadIntent: vi.fn().mockResolvedValue(signedIntent),
      completeUploadIntent: vi.fn().mockReturnValue(completion.promise),
    };
    const transport: DirectUploadTransport = {
      uploadSigned: vi.fn().mockReturnValue(upload.promise),
      uploadResumable: vi.fn(),
    };
    const file = pdfFile();

    render(<UploadZone api={api} canUpload caseId="case-1" transport={transport} />);
    fireEvent.change(screen.getByLabelText("Chọn tài liệu"), {
      target: { files: [file] },
    });

    expect(
      await screen.findByText("Đang tải trực tiếp lên kho tài liệu"),
    ).toBeVisible();
    expect(transport.uploadSigned).toHaveBeenCalledWith(
      signedIntent,
      file,
      expect.objectContaining({ onProgress: expect.any(Function) }),
    );
    expect(api.createUploadIntent).toHaveBeenCalledWith("case-1", {
      fileName: "ho-so-tong-hop.pdf",
      contentType: "application/pdf",
      sizeBytes: file.size,
    });
    expect(api.completeUploadIntent).not.toHaveBeenCalled();
    expect(screen.queryByText("Đang chờ xử lý")).not.toBeInTheDocument();

    upload.resolve();
    expect(await screen.findByText(/Đang xác minh tài liệu/)).toBeVisible();
    expect(api.completeUploadIntent).toHaveBeenCalledWith(
      "intent-1",
      expect.any(String),
    );
    expect(screen.queryByText("Đang chờ xử lý")).not.toBeInTheDocument();

    await act(async () => completion.resolve(completed));
    expect(await screen.findByText("Đang chờ xử lý")).toBeVisible();
  });

  it("uses the in-memory resumable transport selected by the backend", async () => {
    const api = {
      createUploadIntent: vi.fn().mockResolvedValue(resumableIntent),
      completeUploadIntent: vi.fn().mockResolvedValue(completed),
    };
    const transport: DirectUploadTransport = {
      uploadSigned: vi.fn(),
      uploadResumable: vi.fn().mockResolvedValue(undefined),
    };

    render(<UploadZone api={api} canUpload caseId="case-1" transport={transport} />);
    fireEvent.change(screen.getByLabelText("Chọn tài liệu"), {
      target: { files: [pdfFile()] },
    });

    expect(await screen.findByText("Đang chờ xử lý")).toBeVisible();
    expect(transport.uploadResumable).toHaveBeenCalledTimes(1);
    expect(transport.uploadSigned).not.toHaveBeenCalled();
  });

  it("never shows a failed backend verification as registered and offers retry", async () => {
    const api = {
      createUploadIntent: vi.fn().mockResolvedValue(signedIntent),
      completeUploadIntent: vi
        .fn()
        .mockRejectedValue(
          new ApiClientError(422, "UPLOAD_VERIFICATION_FAILED", "invalid", false),
        ),
    };
    const transport: DirectUploadTransport = {
      uploadSigned: vi.fn().mockResolvedValue(undefined),
      uploadResumable: vi.fn(),
    };

    render(<UploadZone api={api} canUpload caseId="case-1" transport={transport} />);
    fireEvent.change(screen.getByLabelText("Chọn tài liệu"), {
      target: { files: [pdfFile()] },
    });

    expect(
      await screen.findByText(
        "Thông tin tài liệu chưa hợp lệ. Vui lòng kiểm tra và thử lại.",
      ),
    ).toBeVisible();
    expect(screen.queryByText("Đang chờ xử lý")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Thử lại ho-so-tong-hop.pdf" })).toBeVisible();
  });

  it("retries ambiguous completion with the same intent and idempotency key without reupload", async () => {
    const api = {
      createUploadIntent: vi.fn().mockResolvedValue(signedIntent),
      completeUploadIntent: vi
        .fn()
        .mockRejectedValueOnce(new TypeError("connection interrupted"))
        .mockResolvedValueOnce(completed),
    };
    const transport: DirectUploadTransport = {
      uploadSigned: vi.fn().mockResolvedValue(undefined),
      uploadResumable: vi.fn(),
    };

    render(<UploadZone api={api} canUpload caseId="case-1" transport={transport} />);
    fireEvent.change(screen.getByLabelText("Chọn tài liệu"), {
      target: { files: [pdfFile()] },
    });
    fireEvent.click(
      await screen.findByRole("button", { name: "Thử lại ho-so-tong-hop.pdf" }),
    );

    expect(await screen.findByText("Đang chờ xử lý")).toBeVisible();
    expect(api.createUploadIntent).toHaveBeenCalledTimes(1);
    expect(transport.uploadSigned).toHaveBeenCalledTimes(1);
    expect(api.completeUploadIntent).toHaveBeenCalledTimes(2);
    expect(api.completeUploadIntent.mock.calls[1]).toEqual(
      api.completeUploadIntent.mock.calls[0],
    );
  });

  it("does not offer cancellation after backend verification starts", async () => {
    const completion = deferred<CompleteUploadResponseDto>();
    const api = {
      createUploadIntent: vi.fn().mockResolvedValue(signedIntent),
      completeUploadIntent: vi.fn().mockReturnValue(completion.promise),
    };
    const transport: DirectUploadTransport = {
      uploadSigned: vi.fn().mockResolvedValue(undefined),
      uploadResumable: vi.fn(),
    };

    render(<UploadZone api={api} canUpload caseId="case-1" transport={transport} />);
    fireEvent.change(screen.getByLabelText("Chọn tài liệu"), {
      target: { files: [pdfFile()] },
    });

    expect(await screen.findByText(/Không thể hủy ở bước này/)).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Hủy tải ho-so-tong-hop.pdf" }),
    ).not.toBeInTheDocument();
    await act(async () => completion.resolve(completed));
  });

  it("retries an interrupted resumable upload from its in-memory upload URL", async () => {
    const resumeUrl = "https://storage.invalid/tus/upload-prior";
    const api = {
      createUploadIntent: vi.fn().mockResolvedValue(resumableIntent),
      completeUploadIntent: vi.fn().mockResolvedValue(completed),
    };
    const uploadResumableMock = vi
      .fn()
      .mockImplementationOnce(
        async (
          _intent: unknown,
          _file: File,
          options: ResumableUploadOptions,
        ) => {
          options.onResumeUrl?.(resumeUrl);
          throw new DirectStorageError(0, "DIRECT_STORAGE_NETWORK_ERROR");
        },
      )
      .mockResolvedValueOnce(undefined);
    const transport: DirectUploadTransport = {
      uploadSigned: vi.fn(),
      uploadResumable: uploadResumableMock,
    };

    render(<UploadZone api={api} canUpload caseId="case-1" transport={transport} />);
    fireEvent.change(screen.getByLabelText("Chọn tài liệu"), {
      target: { files: [pdfFile()] },
    });
    fireEvent.click(
      await screen.findByRole("button", { name: "Thử lại ho-so-tong-hop.pdf" }),
    );

    expect(await screen.findByText("Đang chờ xử lý")).toBeVisible();
    expect(api.createUploadIntent).toHaveBeenCalledTimes(1);
    expect(uploadResumableMock).toHaveBeenCalledTimes(2);
    expect(uploadResumableMock.mock.calls[1][2]).toMatchObject({ resumeUrl });
  });

  it("renders a backend task that requires manual review", async () => {
    const api = {
      createUploadIntent: vi.fn().mockResolvedValue(signedIntent),
      completeUploadIntent: vi.fn().mockResolvedValue({
        outcome: "REGISTERED",
        documentId: "document-1",
        documentVersionId: "version-1",
        task: { id: "task-1", status: "FAILED_MANUAL_REVIEW" },
      }),
    };
    const transport: DirectUploadTransport = {
      uploadSigned: vi.fn().mockResolvedValue(undefined),
      uploadResumable: vi.fn(),
    };

    render(<UploadZone api={api} canUpload caseId="case-1" transport={transport} />);
    fireEvent.change(screen.getByLabelText("Chọn tài liệu"), {
      target: { files: [pdfFile()] },
    });

    expect(await screen.findByText("Cần rà soát thủ công")).toBeVisible();
    expect(screen.queryByText("Đang chờ xử lý")).not.toBeInTheDocument();
  });

  it("fails closed when completion does not identify a registered document", async () => {
    const api = {
      createUploadIntent: vi.fn().mockResolvedValue(signedIntent),
      completeUploadIntent: vi.fn().mockResolvedValue({
        outcome: "INVALID",
      }),
    };
    const transport: DirectUploadTransport = {
      uploadSigned: vi.fn().mockResolvedValue(undefined),
      uploadResumable: vi.fn(),
    };

    render(<UploadZone api={api} canUpload caseId="case-1" transport={transport} />);
    fireEvent.change(screen.getByLabelText("Chọn tài liệu"), {
      target: { files: [pdfFile()] },
    });

    expect(
      await screen.findByText("Không thể hoàn tất yêu cầu. Vui lòng thử lại."),
    ).toBeVisible();
    expect(screen.queryByText("Đang chờ xử lý")).not.toBeInTheDocument();
  });

  it("cancels one file without changing the state of another file", async () => {
    const firstUpload = deferred<void>();
    const secondUpload = deferred<void>();
    const api = {
      createUploadIntent: vi
        .fn()
        .mockResolvedValueOnce(signedIntent)
        .mockResolvedValueOnce({ ...signedIntent, intentId: "intent-3" }),
      completeUploadIntent: vi.fn().mockResolvedValue(completed),
    };
    const transport: DirectUploadTransport = {
      uploadSigned: vi
        .fn()
        .mockReturnValueOnce(firstUpload.promise)
        .mockReturnValueOnce(secondUpload.promise),
      uploadResumable: vi.fn(),
    };
    const secondFile = new File(["synthetic"], "bao-cao.pdf", {
      type: "application/pdf",
    });

    render(<UploadZone api={api} canUpload caseId="case-1" transport={transport} />);
    fireEvent.change(screen.getByLabelText("Chọn tài liệu"), {
      target: { files: [pdfFile(), secondFile] },
    });
    await screen.findAllByText("Đang tải trực tiếp lên kho tài liệu");
    fireEvent.click(
      screen.getByRole("button", { name: "Hủy tải ho-so-tong-hop.pdf" }),
    );

    expect(await screen.findByText("Đã hủy tải lên")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Hủy tải bao-cao.pdf" }),
    ).toBeVisible();
  });

  it("does not start a direct upload from an expired authorization", async () => {
    const api = {
      createUploadIntent: vi.fn().mockResolvedValue({
        ...signedIntent,
        expiresAt: "2020-01-01T00:00:00Z",
      }),
      completeUploadIntent: vi.fn(),
    };
    const transport: DirectUploadTransport = {
      uploadSigned: vi.fn(),
      uploadResumable: vi.fn(),
    };

    render(<UploadZone api={api} canUpload caseId="case-1" transport={transport} />);
    fireEvent.change(screen.getByLabelText("Chọn tài liệu"), {
      target: { files: [pdfFile()] },
    });

    expect(
      await screen.findByText("Phiên tải lên đã hết hạn. Vui lòng thử lại."),
    ).toBeVisible();
    expect(transport.uploadSigned).not.toHaveBeenCalled();
    expect(api.completeUploadIntent).not.toHaveBeenCalled();
  });
});

describe("Vietnamese API errors", () => {
  it.each([
    [401, "Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại."],
    [403, "Bạn không có quyền thực hiện thao tác này trên hồ sơ."],
    [409, "Dữ liệu đã thay đổi hoặc thao tác bị trùng. Vui lòng tải lại."],
    [413, "Tài liệu vượt quá dung lượng được phép."],
    [415, "Định dạng tài liệu chưa được hỗ trợ."],
    [422, "Thông tin tài liệu chưa hợp lệ. Vui lòng kiểm tra và thử lại."],
  ])("maps HTTP %i without exposing backend details", (status, message) => {
    expect(
      getVietnameseApiError(
        new ApiClientError(status, "INTERNAL_DETAIL", "secret detail", false),
      ),
    ).toBe(message);
  });
});

describe("direct Storage transports", () => {
  it("sends signed-upload bytes to the signed Storage URL with XHR progress", async () => {
    const xhr = new FakeXmlHttpRequest();
    const progress = vi.fn();
    const file = pdfFile();

    xhr.onSend = () => {
      xhr.upload.onprogress?.({ lengthComputable: true, loaded: file.size, total: file.size } as ProgressEvent);
      xhr.status = 200;
      xhr.onload?.(new ProgressEvent("load"));
    };

    await uploadSigned(signedIntent, file, {
      onProgress: progress,
      signal: new AbortController().signal,
      xhrFactory: () => xhr as unknown as XMLHttpRequest,
    });

    expect(xhr.open).toHaveBeenCalledWith(
      "PUT",
      "https://storage.invalid/signed-object",
      true,
    );
    expect(xhr.setRequestHeader).toHaveBeenCalledWith(
      "x-upload-token",
      "ephemeral-value",
    );
    expect(xhr.sentBody).toBe(file);
    expect(progress).toHaveBeenLastCalledWith(100);
  });

  it("retains a sanitized direct-storage HTTP status for Vietnamese mapping", async () => {
    const xhr = new FakeXmlHttpRequest();
    xhr.onSend = () => {
      xhr.status = 413;
      xhr.responseText = "provider-secret-detail";
      xhr.onload?.(new ProgressEvent("load"));
    };

    const request = uploadSigned(signedIntent, pdfFile(), {
      onProgress: vi.fn(),
      signal: new AbortController().signal,
      xhrFactory: () => xhr as unknown as XMLHttpRequest,
    });

    await expect(request).rejects.toMatchObject({
      name: "DirectStorageError",
      status: 413,
      message: "DIRECT_STORAGE_REQUEST_FAILED",
    });
    await expect(request).rejects.not.toThrow(/provider-secret-detail/);
    expect(getVietnameseApiError(new DirectStorageError(415))).toBe(
      "Định dạng tài liệu chưa được hỗ trợ.",
    );
  });

  it("uses TUS without writing its authorization or upload URL to localStorage", async () => {
    const requests: FakeXmlHttpRequest[] = [];
    const localStorageWrite = vi.spyOn(Storage.prototype, "setItem");
    const onResumeUrl = vi.fn();
    const file = pdfFile();
    const intentWithStorageMetadata: UploadIntentDto = {
      ...resumableIntent,
      headers: {
        ...resumableIntent.headers,
        "Upload-Metadata": "bucketName c3ludGhldGlj,objectName b3BhcXVlLWtleQ==",
      },
    };

    if (intentWithStorageMetadata.mode !== "RESUMABLE") throw new Error("test setup");
    await uploadResumable(intentWithStorageMetadata, file, {
      onProgress: vi.fn(),
      onResumeUrl,
      signal: new AbortController().signal,
      xhrFactory: () => {
        const xhr = new FakeXmlHttpRequest();
        requests.push(xhr);
        xhr.onSend = () => {
          if (requests.length === 1) {
            xhr.status = 201;
            xhr.responseHeaders.Location = "/tus/upload-1";
          } else {
            xhr.status = 204;
            xhr.responseHeaders["Upload-Offset"] = String(file.size);
            xhr.upload.onprogress?.({
              lengthComputable: true,
              loaded: file.size,
              total: file.size,
            } as ProgressEvent);
          }
          xhr.onload?.(new ProgressEvent("load"));
        };
        return xhr as unknown as XMLHttpRequest;
      },
    });

    expect(requests).toHaveLength(2);
    expect(onResumeUrl).toHaveBeenCalledWith(
      "https://storage.invalid/tus/upload-1",
    );
    expect(requests[0].open).toHaveBeenCalledWith(
      "POST",
      "https://storage.invalid/tus",
      true,
    );
    expect(requests[1].open).toHaveBeenCalledWith(
      "PATCH",
      "https://storage.invalid/tus/upload-1",
      true,
    );
    expect(requests[1].setRequestHeader).toHaveBeenCalledWith(
      "authorization",
      "ephemeral-value",
    );
    expect(requests[0].setRequestHeader).toHaveBeenCalledWith(
      "Upload-Metadata",
      "bucketName c3ludGhldGlj,objectName b3BhcXVlLWtleQ==",
    );
    expect(localStorageWrite).not.toHaveBeenCalled();
    localStorageWrite.mockRestore();
  });

  it("resumes an interrupted TUS upload from the server HEAD offset", async () => {
    const requests: FakeXmlHttpRequest[] = [];
    const file = pdfFile();

    if (resumableIntent.mode !== "RESUMABLE") throw new Error("test setup");
    await uploadResumable(resumableIntent, file, {
      onProgress: vi.fn(),
      resumeUrl: "https://storage.invalid/tus/upload-prior",
      signal: new AbortController().signal,
      xhrFactory: () => {
        const xhr = new FakeXmlHttpRequest();
        requests.push(xhr);
        xhr.onSend = () => {
          if (requests.length === 1) {
            xhr.status = 200;
            xhr.responseHeaders["Upload-Offset"] = "5";
          } else {
            xhr.status = 204;
            xhr.responseHeaders["Upload-Offset"] = String(file.size);
          }
          xhr.onload?.(new ProgressEvent("load"));
        };
        return xhr as unknown as XMLHttpRequest;
      },
    });

    expect(requests).toHaveLength(2);
    expect(requests[0].open).toHaveBeenCalledWith(
      "HEAD",
      "https://storage.invalid/tus/upload-prior",
      true,
    );
    expect(requests[1].open).toHaveBeenCalledWith(
      "PATCH",
      "https://storage.invalid/tus/upload-prior",
      true,
    );
    expect(requests[1].setRequestHeader).toHaveBeenCalledWith("Upload-Offset", "5");
    expect((requests[1].sentBody as Blob).size).toBe(file.size - 5);
  });

  it.each([undefined, "not-a-number", "-1", "1.5", "999"])(
    "fails closed on invalid TUS HEAD offset %s",
    async (offset) => {
      const xhr = new FakeXmlHttpRequest();
      xhr.onSend = () => {
        xhr.status = 200;
        if (offset !== undefined) xhr.responseHeaders["Upload-Offset"] = offset;
        xhr.onload?.(new ProgressEvent("load"));
      };
      if (resumableIntent.mode !== "RESUMABLE") throw new Error("test setup");

      await expect(
        uploadResumable(resumableIntent, pdfFile(), {
          onProgress: vi.fn(),
          resumeUrl: "https://storage.invalid/tus/upload-prior",
          signal: new AbortController().signal,
          xhrFactory: () => xhr as unknown as XMLHttpRequest,
        }),
      ).rejects.toMatchObject({ message: "TUS_OFFSET_INVALID" });
    },
  );

  it.each([undefined, "0", "999"])(
    "fails closed on missing, non-monotonic, or out-of-range PATCH offset %s",
    async (offset) => {
      const requests: FakeXmlHttpRequest[] = [];
      if (resumableIntent.mode !== "RESUMABLE") throw new Error("test setup");

      await expect(
        uploadResumable(resumableIntent, pdfFile(), {
          onProgress: vi.fn(),
          resumeUrl: "https://storage.invalid/tus/upload-prior",
          signal: new AbortController().signal,
          xhrFactory: () => {
            const xhr = new FakeXmlHttpRequest();
            requests.push(xhr);
            xhr.onSend = () => {
              xhr.status = requests.length === 1 ? 200 : 204;
              if (requests.length === 1) xhr.responseHeaders["Upload-Offset"] = "0";
              else if (offset !== undefined) xhr.responseHeaders["Upload-Offset"] = offset;
              xhr.onload?.(new ProgressEvent("load"));
            };
            return xhr as unknown as XMLHttpRequest;
          },
        }),
      ).rejects.toMatchObject({ message: "TUS_OFFSET_INVALID" });
    },
  );
});

class FakeXmlHttpRequest {
  onabort: ((event: ProgressEvent) => void) | null = null;
  onerror: ((event: ProgressEvent) => void) | null = null;
  onload: ((event: ProgressEvent) => void) | null = null;
  onSend: (() => void) | null = null;
  responseHeaders: Record<string, string> = {};
  responseText = "";
  sentBody: Document | XMLHttpRequestBodyInit | null = null;
  status = 0;
  upload = {
    onprogress: null as ((event: ProgressEvent) => void) | null,
  };
  abort = vi.fn(() => this.onabort?.(new ProgressEvent("abort")));
  getResponseHeader = vi.fn((name: string) => {
    const entry = Object.entries(this.responseHeaders).find(
      ([key]) => key.toLowerCase() === name.toLowerCase(),
    );
    return entry?.[1] ?? null;
  });
  open = vi.fn();
  send = vi.fn((body: Document | XMLHttpRequestBodyInit | null) => {
    this.sentBody = body;
    queueMicrotask(() => this.onSend?.());
  });
  setRequestHeader = vi.fn();
}
