"use client";

import React, { useCallback, useEffect, useState } from "react";

import { creditOpsApi, getVietnameseApiError } from "../../lib/api/client";
import type { CreditCaseDto } from "../../lib/api/contracts";
import { CaseNav } from "../shell/case-nav";
import { UploadZone } from "../uploads/upload-zone";

export function CaseIntake({ caseId }: { caseId: string }) {
  const [creditCase, setCreditCase] = useState<CreditCaseDto | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setCreditCase(await creditOpsApi.getCase(caseId));
    } catch (requestError) {
      setError(getVietnameseApiError(requestError));
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div aria-busy="true" aria-label="Đang tải quyền hồ sơ" className="case-skeleton" role="status">
        <span className="skeleton-line skeleton-line-wide" />
        <span className="skeleton-line" />
      </div>
    );
  }

  if (error || !creditCase) {
    return (
      <div className="state-panel" role="alert">
        <p>{error ?? "Không thể đọc hồ sơ."}</p>
        <button className="button button-secondary" onClick={() => void load()} type="button">
          Thử tải lại
        </button>
      </div>
    );
  }

  return (
    <>
      <CaseNav caseId={caseId} />
      <div className="page-heading">
        <p className="eyebrow">Hồ sơ · phiên bản {creditCase.version}</p>
        <h1>Tiếp nhận tài liệu</h1>
        <p>
          Hồ sơ này chỉ dùng dữ liệu tổng hợp cho trình diễn. {creditCase.purpose ?? "Mục đích vay vốn chưa được ghi nhận."} Tài liệu tải lên là dữ liệu không tin cậy cho đến khi được kiểm tra và xác minh.
        </p>
      </div>
      <UploadZone caseId={caseId} canUpload={creditCase.capabilities.canUpload} />
    </>
  );
}
