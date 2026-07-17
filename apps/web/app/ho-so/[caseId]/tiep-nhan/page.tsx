import React from "react";

import { CaseIntake } from "../../../../components/cases/case-intake";

interface IntakePageProps {
  params: Promise<{ caseId: string }>;
}

export default async function IntakePage({ params }: IntakePageProps) {
  const { caseId } = await params;
  return <CaseIntake caseId={caseId} />;
}
