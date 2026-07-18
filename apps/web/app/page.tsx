import React from "react";

import {
  SYNTHETIC_DATA_NOTICE,
  SYNTHETIC_DATA_NOTICE_VI,
} from "../components/shell/synthetic-data-notice";

export default function Home() {
  return (
    <main>
      <section aria-labelledby="intake-title" className="intake-panel">
        <p className="eyebrow">SHB CreditOps EvidenceGraph</p>
        <h1 id="intake-title">Tiếp nhận hồ sơ tín dụng</h1>
        <p className="boundary">
          Không gian chuẩn bị và rà soát hồ sơ vốn lưu động dành cho nhân sự có thẩm
          quyền. Hệ thống không phê duyệt hoặc từ chối cấp tín dụng.
        </p>
        <aside aria-label="Thông báo dữ liệu tổng hợp" className="notice">
          <strong>Phạm vi dữ liệu thử nghiệm</strong>
          <span>{SYNTHETIC_DATA_NOTICE_VI}</span>
          <span lang="en">{SYNTHETIC_DATA_NOTICE}</span>
        </aside>
      </section>
    </main>
  );
}
