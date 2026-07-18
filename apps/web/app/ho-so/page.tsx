import React from "react";

import { CaseList } from "../../components/cases/case-list";

export default function CasesPage() {
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Không gian cán bộ tiếp nhận</p>
          <h1>Hồ sơ được phân công</h1>
          <p>Theo dõi hồ sơ tổng hợp dùng cho trình diễn và tiếp nhận tài liệu theo quyền do backend cấp cho từng hồ sơ.</p>
        </div>
      </div>
      <CaseList />
    </>
  );
}
