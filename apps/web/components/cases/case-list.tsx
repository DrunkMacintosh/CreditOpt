"use client";

import Link from "next/link";
import React, { useCallback, useEffect, useState } from "react";

import { creditOpsApi, getVietnameseApiError } from "../../lib/api/client";
import type { CreditCaseListDto } from "../../lib/api/contracts";

interface CaseListProps {
  api?: Pick<typeof creditOpsApi, "listCases">;
}

export function CaseList({ api = creditOpsApi }: CaseListProps) {
  const [collection, setCollection] = useState<CreditCaseListDto | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setCollection(await api.listCases());
    } catch (requestError) {
      setError(getVietnameseApiError(requestError));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div
        aria-busy="true"
        aria-label="Đang tải danh sách hồ sơ"
        className="case-skeleton"
        role="status"
      >
        <span className="skeleton-line skeleton-line-wide" />
        <span className="skeleton-line" />
        <span className="skeleton-line skeleton-line-short" />
      </div>
    );
  }

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

  if (!collection) {
    return null;
  }

  if (collection.items.length === 0) {
    return (
      <div className="state-panel">
        <h2>Chưa có hồ sơ được phân công</h2>
        <p>Không có hồ sơ trong phạm vi phân công. Chỉ sử dụng dữ liệu tổng hợp dùng cho trình diễn.</p>
        {collection.capabilities.canCreateCase ? (
          <Link className="button button-primary" href="/ho-so/tao-moi">
            Tạo hồ sơ
          </Link>
        ) : (
          <p className="permission-note">Bạn không có quyền tạo hồ sơ minh họa.</p>
        )}
      </div>
    );
  }

  return (
    <>
      {collection.capabilities.canCreateCase ? (
        <div className="collection-actions">
          <Link className="button button-primary" href="/ho-so/tao-moi">
            Tạo hồ sơ
          </Link>
        </div>
      ) : null}
      <ul aria-label="Hồ sơ được phân công" className="case-grid">
      {collection.items.map((creditCase) => {
        const purpose = creditCase.purpose ?? "Chưa có mục đích vay vốn";
        return (
          <li className="case-card" key={creditCase.id}>
            <article aria-labelledby={`case-${creditCase.id}`}>
              <header className="case-card-header">
                <div>
                  <p className="case-kicker">Hồ sơ · phiên bản {creditCase.version}</p>
                  <h2 id={`case-${creditCase.id}`}>{purpose}</h2>
                </div>
                {creditCase.workflowState ? (
                  <span className="status-chip">
                    {workflowStateLabel(creditCase.workflowState)}
                  </span>
                ) : null}
              </header>
              <dl className="case-facts">
                <div>
                  <dt>Số tiền đề nghị</dt>
                  <dd>
                    {creditCase.requestedAmount
                      ? formatAmount(creditCase.requestedAmount)
                      : "Chưa có dữ liệu"}
                  </dd>
                </div>
                <div>
                  <dt>Cập nhật</dt>
                  <dd>
                    {creditCase.updatedAt
                      ? formatDate(creditCase.updatedAt)
                      : "Chưa có dữ liệu"}
                  </dd>
                </div>
              </dl>
              <footer className="case-actions">
                {creditCase.capabilities.canUpload ? (
                  <Link
                    aria-label={`Tiếp nhận tài liệu — ${purpose}`}
                    className="button button-primary"
                    href={`/ho-so/${encodeURIComponent(creditCase.id)}/tiep-nhan`}
                  >
                    Tiếp nhận tài liệu
                  </Link>
                ) : (
                  <span className="permission-note">Không có quyền tải tài liệu</span>
                )}
              </footer>
            </article>
          </li>
        );
      })}
      </ul>
    </>
  );
}

function formatAmount(amount: string): string {
  if (!/^\d+$/.test(amount)) return amount;
  try {
    return `${new Intl.NumberFormat("vi-VN").format(BigInt(amount))} VND`;
  } catch {
    return amount;
  }
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function workflowStateLabel(value: string): string {
  const labels: Readonly<Record<string, string>> = {
    INTAKE: "Đang tiếp nhận",
    READY_FOR_SPECIALIST_REVIEW: "Sẵn sàng bàn giao",
    COMPLETED: "Đã hoàn tất tiếp nhận",
  };
  return labels[value] ?? "Trạng thái không xác định";
}
