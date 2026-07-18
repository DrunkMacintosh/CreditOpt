import React from "react";

export const SYNTHETIC_DATA_NOTICE =
  "All customer data, policies, documents, and banking-system responses in this project are synthetic and created solely for demonstration.";

export function SyntheticDataNotice() {
  return (
    <aside aria-label="Thông báo dữ liệu tổng hợp" className="synthetic-notice">
      <span aria-hidden="true" className="notice-mark">S</span>
      <div>
        <strong>Dữ liệu tổng hợp dùng cho trình diễn</strong>
        <p>{SYNTHETIC_DATA_NOTICE}</p>
      </div>
    </aside>
  );
}
