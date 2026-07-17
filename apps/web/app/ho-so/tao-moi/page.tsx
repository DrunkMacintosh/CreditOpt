import React from "react";

import { CreateCaseForm } from "../../../components/cases/create-case-form";

export default function CreateCasePage() {
  return (
    <div className="content-narrow">
      <div className="page-heading">
        <p className="eyebrow">Nhu cầu cấp vốn</p>
        <h1>Tạo hồ sơ</h1>
        <p>Chỉ ghi nhận thông tin cần thiết đã được cán bộ tiếp nhận xác định. Trường chưa biết được để trống, không tự suy đoán.</p>
      </div>
      <CreateCaseForm />
    </div>
  );
}
