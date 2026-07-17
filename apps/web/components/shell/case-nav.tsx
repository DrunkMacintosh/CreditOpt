import Link from "next/link";
import React from "react";

export function CaseNav({ caseId }: { caseId: string }) {
  return (
    <nav aria-label="Điều hướng hồ sơ" className="case-nav">
      <Link href="/ho-so">Danh sách hồ sơ</Link>
      <span aria-hidden="true">/</span>
      <span>Tiếp nhận tài liệu</span>
      <span className="case-reference">Mã: {shortReference(caseId)}</span>
    </nav>
  );
}

function shortReference(caseId: string): string {
  return caseId.length > 12 ? `${caseId.slice(0, 8)}…` : caseId;
}
