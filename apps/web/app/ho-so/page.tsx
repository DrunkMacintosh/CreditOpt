import Link from "next/link";
import React from "react";

import { CaseList } from "../../components/cases/case-list";

export default function CasesPage() {
  return (
    <>
      <div className="page-heading page-heading-with-action">
        <div>
          <p className="eyebrow">Không gian cán bộ tiếp nhận</p>
          <h1>Hồ sơ được phân công</h1>
          <p>Theo dõi nhu cầu cấp vốn và tiếp nhận tài liệu theo quyền do backend cấp cho từng hồ sơ.</p>
        </div>
        <Link className="button button-primary" href="/ho-so/tao-moi">
          Tạo hồ sơ
        </Link>
      </div>
      <CaseList />
    </>
  );
}
