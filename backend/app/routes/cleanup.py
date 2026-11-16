from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.core.auth import require_active_user, require_admin_user
from app.models.user import User
from app.schemas.cleanup import (
    AssignmentNotificationApproval,
    CleanupOperationAssignment,
    CleanupOperationCompletion,
    CleanupOperationCreate,
    CleanupOperationStatusUpdate,
    EvidenceVerificationUpdate,
    EvidenceType,
)
from app.services.cleanup_service import CleanupService
from app.services.private_media import PrivateMediaError
from app.services.recommendation_service import RecommendationService


router = APIRouter(dependencies=[Depends(require_active_user)])


@router.get("/recommendations", summary="Recommend inspection, preventive cleanup, and monitoring actions")
async def get_cleanup_recommendations(
    ecological_risk: Optional[float] = Query(None, ge=0, le=100),
    human_exposure: Optional[float] = Query(None, ge=0, le=100),
    cleanup_feasibility: Optional[float] = Query(None, ge=0, le=100),
    limit: int = Query(100, ge=1, le=500),
):
    return await RecommendationService.get_cleanup_recommendations(
        ecological_risk=ecological_risk,
        human_exposure=human_exposure,
        cleanup_feasibility=cleanup_feasibility,
        limit=limit,
    )


@router.get("/operations", summary="List cleanup response operations")
async def list_operations(
    status: Optional[str] = Query(None, pattern="^(PLANNED|ASSIGNED|INSPECTION_SCHEDULED|CLEANUP_STARTED|COMPLETED|CANCELLED)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    return await CleanupService.list_operations(status=status, skip=skip, limit=limit)


@router.post("/operations", status_code=201, summary="Create an operation from a current recommendation")
async def create_operation(
    body: CleanupOperationCreate,
    current_user: User = Depends(require_admin_user),
):
    try:
        return await CleanupService.create_operation(
            body.recommendation_id, body.scheduled_at, current_user.user_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/operations/{operation_id}", summary="Get operation, status history, and evidence")
async def get_operation(operation_id: str):
    operation = await CleanupService.get_operation(operation_id)
    if operation is None:
        raise HTTPException(status_code=404, detail="Cleanup operation not found.")
    operation["evidence"] = await CleanupService.list_evidence(operation_id)
    return operation


@router.patch("/operations/{operation_id}/assignment", summary="Assign a verified organization and coordinator")
async def assign_operation(
    operation_id: str,
    body: CleanupOperationAssignment,
    current_user: User = Depends(require_admin_user),
):
    try:
        return await CleanupService.assign_operation(
            operation_id,
            body.organization_id,
            body.responsible_coordinator_user_id,
            body.scheduled_at,
            current_user.user_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/operations/{operation_id}/status", summary="Apply an authorized operation status transition")
async def update_operation_status(
    operation_id: str,
    body: CleanupOperationStatusUpdate,
    current_user: User = Depends(require_admin_user),
):
    try:
        return await CleanupService.update_status(
            operation_id, body.status, body.reason, current_user.user_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/operations/{operation_id}/evidence", status_code=201, summary="Record inspection notes or upload operation evidence")
async def submit_operation_evidence(
    operation_id: str,
    evidence_type: EvidenceType = Form(...),
    notes: Optional[str] = Form(None, max_length=4000),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_admin_user),
):
    try:
        return await CleanupService.add_evidence(
            operation_id, evidence_type, notes, file, current_user.user_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PrivateMediaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        if file is not None:
            await file.close()


@router.get("/evidence/{evidence_id}/download", summary="Download protected operation evidence")
async def download_operation_evidence(
    evidence_id: str,
    _current_user: User = Depends(require_admin_user),
):
    evidence = await CleanupService.get_evidence_media(evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Operation evidence image not found.")
    media = evidence["media"]
    return FileResponse(
        media["path"],
        media_type=media["content_type"],
        filename=f"cleanup-evidence-{evidence_id}.{media['extension']}",
        headers={"Cache-Control": "private, no-store"},
    )


@router.patch("/operations/{operation_id}/evidence/{evidence_id}/verification", summary="Review submitted operation evidence")
async def verify_operation_evidence(
    operation_id: str,
    evidence_id: str,
    body: EvidenceVerificationUpdate,
    current_user: User = Depends(require_admin_user),
):
    try:
        result = await CleanupService.verify_evidence(
            operation_id,
            evidence_id,
            body.status,
            body.reason,
            current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Operation or evidence not found.")
    return result


@router.post("/operations/{operation_id}/completion", summary="Record cleanup completion and quantity evidence")
async def complete_operation(
    operation_id: str,
    body: CleanupOperationCompletion,
    current_user: User = Depends(require_admin_user),
):
    try:
        return await CleanupService.complete_operation(
            operation_id, body, current_user.user_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/operations/{operation_id}/notifications", summary="Approve and send an assignment notification")
async def send_assignment_notification(
    operation_id: str,
    body: AssignmentNotificationApproval,
    current_user: User = Depends(require_admin_user),
):
    try:
        return await CleanupService.send_assignment_notification(
            operation_id, body.approved, current_user.user_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/operations/{operation_id}/notifications", summary="List assignment notification status")
async def list_assignment_notifications(
    operation_id: str,
    _current_user: User = Depends(require_admin_user),
):
    return await CleanupService.list_notifications(operation_id)


@router.patch("/notifications/{notification_id}/acknowledge", summary="Record assignment acknowledgment")
async def acknowledge_assignment(
    notification_id: str,
    current_user: User = Depends(require_admin_user),
):
    result = await CleanupService.acknowledge_assignment(
        notification_id, current_user.user_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Sent assignment notification not found.")
    return result


@router.get("/analytics", summary="Summarize completed cleanup operations and quantities")
async def get_cleanup_analytics():
    return await CleanupService.get_analytics()
