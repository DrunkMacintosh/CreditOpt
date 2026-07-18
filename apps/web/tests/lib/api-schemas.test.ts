import { describe, expect, it } from "vitest";

import {
  parseCompleteUpload,
  parseCreditCase,
  parseCreditCaseList,
  parseUploadIntent,
} from "../../lib/api/schemas";

const rawCase = {
  id: "case-synthetic",
  version: 1,
  assignedOfficerId: "officer-synthetic",
  requestedAmount: "5000000000",
  purpose: "Nhu cầu vốn lưu động tổng hợp",
  capabilities: {
    canUpload: true,
    canConfirm: true,
    canCompleteIntake: false,
  },
};

describe("case schemas", () => {
  it("requires every per-case capability instead of defaulting missing authority", () => {
    expect(() =>
      parseCreditCase({
        ...rawCase,
        capabilities: { canConfirm: true, canCompleteIntake: true },
      }),
    ).toThrow(/canUpload/);
  });

  it("requires an envelope-level canCreateCase capability", () => {
    expect(() => parseCreditCaseList({ items: [rawCase], nextCursor: null })).toThrow(
      /canCreateCase/,
    );
    expect(() => parseCreditCaseList([rawCase])).toThrow(/danh sách hồ sơ/);
  });

  it("normalizes the strict collection envelope", () => {
    expect(
      parseCreditCaseList({
        items: [rawCase],
        nextCursor: null,
        capabilities: { canCreateCase: false },
      }),
    ).toMatchObject({
      items: [{ id: "case-synthetic" }],
      nextCursor: null,
      capabilities: { canCreateCase: false },
    });
  });
});

describe("upload schemas", () => {
  it.each([
    { mode: "signed", method: "PUT" },
    { mode: "SIGNED", method: "put" },
    { mode: "resumable" },
  ])("rejects non-canonical upload discriminants %#", (variant) => {
    expect(() =>
      parseUploadIntent({
        ...variant,
        intentId: "intent-canonical",
        expiresAt: "2099-01-01T00:00:00Z",
        uploadUrl: "https://storage.invalid/object",
        headers: {
          "Upload-Metadata": "bucketName cHJpdmF0ZQ==,objectName b3BhcXVl",
        },
      }),
    ).toThrow();
  });

  it("requires an explicit signed method", () => {
    expect(() =>
      parseUploadIntent({
        mode: "SIGNED",
        intentId: "intent-1",
        expiresAt: "2099-01-01T00:00:00Z",
        uploadUrl: "https://storage.invalid/object",
        headers: {},
      }),
    ).toThrow(/phương thức/i);
  });

  it("requires resumable object binding in a case-insensitive Upload-Metadata header", () => {
    const base = {
      mode: "RESUMABLE",
      intentId: "intent-2",
      expiresAt: "2099-01-01T00:00:00Z",
      uploadUrl: "https://storage.invalid/tus",
      headers: { authorization: "temporary" },
    };
    expect(() => parseUploadIntent(base)).toThrow(/bucketName.*objectName/i);
    expect(
      parseUploadIntent({
        ...base,
        headers: {
          authorization: "temporary",
          "upload-metadata": "bucketName cHJpdmF0ZQ==,objectName b3BhcXVl",
        },
      }),
    ).toMatchObject({ mode: "RESUMABLE", intentId: "intent-2" });
  });

  it("rejects any direct-upload authorization that enables upsert", () => {
    expect(() =>
      parseUploadIntent({
        mode: "SIGNED",
        intentId: "intent-upsert",
        expiresAt: "2099-01-01T00:00:00Z",
        uploadUrl: "https://storage.invalid/object",
        method: "PUT",
        headers: { "x-upsert": "true" },
      }),
    ).toThrow(/upsert/i);
  });

  it("accepts only an exact duplicate or registered completion variant", () => {
    expect(
      parseCompleteUpload({
        outcome: "DUPLICATE",
        duplicateOfDocumentId: "document-existing",
      }),
    ).toEqual({ outcome: "DUPLICATE", duplicateOfDocumentId: "document-existing" });
    expect(
      parseCompleteUpload({
        outcome: "REGISTERED",
        documentId: "document-1",
        documentVersionId: "version-1",
        task: { id: "task-1", status: "PENDING" },
      }),
    ).toMatchObject({ outcome: "REGISTERED", documentId: "document-1" });
  });

  it.each([
    {},
    { outcome: "DUPLICATE", duplicateOfDocumentId: "existing", documentId: "new" },
    {
      outcome: "REGISTERED",
      documentId: "new",
      documentVersionId: "version",
      duplicateOfDocumentId: "existing",
      task: { id: "task", status: "PENDING" },
    },
    { outcome: "REGISTERED", documentId: "new", documentVersionId: "version" },
  ])("rejects ambiguous completion shape %#", (value) => {
    expect(() => parseCompleteUpload(value)).toThrow();
  });
});
