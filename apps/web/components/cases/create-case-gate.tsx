"use client";

import React, { useCallback, useEffect, useState } from "react";

import { creditOpsApi, getVietnameseApiError } from "../../lib/api/client";
import type { CaseApi } from "../../lib/api/contracts";
import { CreateCaseForm } from "./create-case-form";

interface CreateCaseGateProps {
  api?: Pick<CaseApi, "listCases" | "createCase">;
}

export function CreateCaseGate({ api = creditOpsApi }: CreateCaseGateProps) {
  const [canCreateCase, setCanCreateCase] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setCanCreateCase(null);
    setError(null);
    try {
      const collection = await api.listCases();
      setCanCreateCase(collection.capabilities.canCreateCase);
    } catch (requestError) {
      setError(getVietnameseApiError(requestError));
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <div className="state-panel" role="alert">
        <p>{error}</p>
        <button className="button button-secondary" onClick={() => void load()} type="button">
          Thử tải lại
        </button>
      </div>
    );
  }

  if (canCreateCase === null) {
    return (
      <div aria-busy="true" aria-label="Đang kiểm tra quyền tạo hồ sơ" className="case-skeleton" role="status">
        <span className="skeleton-line skeleton-line-wide" />
        <span className="skeleton-line" />
      </div>
    );
  }

  return <CreateCaseForm api={api} canCreateCase={canCreateCase} />;
}
