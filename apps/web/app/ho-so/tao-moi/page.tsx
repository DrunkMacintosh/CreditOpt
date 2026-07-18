import React from "react";

import { CreateCaseGate } from "../../../components/cases/create-case-gate";

export default function CreateCasePage() {
  return (
    <div className="content-narrow">
      <div className="page-heading">
        <p className="eyebrow">Nhu cầu cấp vốn</p>
        <h1>Tạo hồ sơ</h1>
        <p>Chỉ dùng dữ liệu tổng hợp được tạo cho trình diễn. Không nhập dữ liệu khách hàng thật và không tự suy đoán trường chưa biết.</p>
      </div>
      <CreateCaseGate />
    </div>
  );
}
