"""Read-only reviewer-output API: latest assessment + its handoff status.

Same auth pattern as ``api/underwriting.py``: a case-participant role is
required, row access is the case-assignment check, and an unassigned actor
receives an indistinguishable 404.  There is no write surface here — the
assessment store is append-only and written exclusively by the worker.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from creditops.api.auth import require_actor
from creditops.api.errors import ApiException
from creditops.application.orchestration.roles import CASE_PARTICIPANT_ROLES
from creditops.application.ports.legal import LegalRepository
from creditops.application.unit_of_work import ActorContext

router = APIRouter(prefix="/api/v1/cases/{case_id}/legal", tags=["legal"])


class HandoffStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    handoff_id: UUID = Field(serialization_alias="handoffId")
    state: str
    created_at: datetime = Field(serialization_alias="createdAt")


class LegalAssessmentResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    assessment_id: UUID = Field(serialization_alias="assessmentId")
    case_id: UUID = Field(serialization_alias="caseId")
    case_version: int = Field(serialization_alias="caseVersion")
    agent_role: str = Field(serialization_alias="agentRole")
    execution_id: UUID = Field(serialization_alias="executionId")
    prompt_version: str = Field(serialization_alias="promptVersion")
    created_at: datetime = Field(serialization_alias="createdAt")
    assessment: dict[str, object]
    handoff: HandoffStatusResponse | None


Actor = Annotated[ActorContext, Depends(require_actor)]


def _require_participant(actor: ActorContext) -> None:
    if not (CASE_PARTICIPANT_ROLES & actor.roles):
        raise ApiException(
            status_code=403,
            code="INSUFFICIENT_ROLE",
            message_vi="Bạn không có vai trò tham gia hồ sơ được yêu cầu.",
        )


def _repository(request: Request) -> LegalRepository:
    repository = getattr(request.app.state, "legal_repository", None)
    if repository is None:
        raise ApiException(
            status_code=503,
            code="LEGAL_SERVICE_UNAVAILABLE",
            message_vi="Dịch vụ pháp lý, tuân thủ và tài sản bảo đảm chưa sẵn sàng.",
            retryable=True,
        )
    return cast(LegalRepository, repository)


async def _assert_case_access(
    request: Request, actor: ActorContext, case_id: UUID
) -> None:
    """Fail closed with an indistinguishable 404 for unassigned actors."""
    uow_factory = getattr(request.app.state, "uow_factory", None)
    if uow_factory is None:
        raise ApiException(
            status_code=503,
            code="CASE_SERVICE_UNAVAILABLE",
            message_vi="Dịch vụ hồ sơ chưa sẵn sàng.",
            retryable=True,
        )
    async with uow_factory(actor) as uow:
        record = await uow.cases.get_assigned(case_id, actor.actor_id)
    if record is None:
        raise ApiException(
            status_code=404,
            code="CASE_NOT_ACCESSIBLE",
            message_vi="Không tìm thấy hồ sơ hoặc bạn không có quyền truy cập.",
        )


@router.get("", response_model=LegalAssessmentResponse)
async def get_legal_assessment(
    case_id: UUID,
    actor: Actor,
    request: Request,
) -> LegalAssessmentResponse:
    _require_participant(actor)
    await _assert_case_access(request, actor, case_id)
    record = await _repository(request).load_latest_assessment(case_id)
    if record is None:
        raise ApiException(
            status_code=404,
            code="LEGAL_ASSESSMENT_NOT_AVAILABLE",
            message_vi="Chưa có bản đánh giá pháp lý cho hồ sơ này.",
        )
    return LegalAssessmentResponse(
        assessment_id=record.assessment_id,
        case_id=record.case_id,
        case_version=record.case_version,
        agent_role=record.agent_role,
        execution_id=record.execution_id,
        prompt_version=record.prompt_version,
        created_at=record.created_at,
        assessment=dict(record.assessment),
        handoff=(
            HandoffStatusResponse(
                handoff_id=record.handoff_id,
                state=record.handoff_state,
                created_at=record.handoff_created_at,
            )
            if record.handoff_id is not None
            and record.handoff_state is not None
            and record.handoff_created_at is not None
            else None
        ),
    )
