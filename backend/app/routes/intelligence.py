from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_active_user, require_admin_user
from app.models.user import User
from app.schemas.intelligence import (
    AlertStatus,
    AlertStatusUpdate,
    NotificationAcknowledgment,
    NotificationApproval,
    OrganizationCreate,
    OrganizationVerificationUpdate,
)
from app.services.intelligence_service import IntelligenceService


router = APIRouter(dependencies=[Depends(require_active_user)])


@router.get("/trends", summary="Compare measured pollution in adjacent equal windows")
async def get_pollution_trends(
    window_days: int = Query(90, ge=7, le=3650),
):
    """Return observation-backed spatial trends; this endpoint does not forecast."""
    try:
        return await IntelligenceService.get_trends(window_days=window_days)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/assess", summary="Refresh measured trends and synchronize high-risk alerts")
async def assess_pollution_risk():
    """Reassess available observations; no forecast or external notification is created."""
    try:
        return await IntelligenceService.assess()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/alerts", summary="List pollution early-warning alerts")
async def list_alerts(
    status: Optional[AlertStatus] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    return await IntelligenceService.list_alerts(status=status, limit=limit)


@router.patch("/alerts/{alert_id}/status", summary="Update an alert status")
async def update_alert_status(
    alert_id: str,
    body: AlertStatusUpdate,
    current_user: User = Depends(require_active_user),
):
    try:
        result = await IntelligenceService.update_alert_status(
            alert_id,
            body.status,
            current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return result


@router.get("/organizations", summary="List verified environmental organizations")
async def list_organizations(
    include_unverified: bool = Query(False),
    current_user: User = Depends(require_active_user),
):
    if include_unverified and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator authorization required.")
    return {"data": await IntelligenceService.list_organizations(include_unverified)}


@router.post("/organizations", status_code=201, summary="Register an environmental organization")
async def create_organization(
    body: OrganizationCreate,
    current_user: User = Depends(require_admin_user),
):
    try:
        return await IntelligenceService.create_organization(
            body.model_dump(),
            current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/organizations/{organization_id}/verification", summary="Verify or unverify an organization")
async def verify_organization(
    organization_id: str,
    body: OrganizationVerificationUpdate,
    current_user: User = Depends(require_admin_user),
):
    result = await IntelligenceService.verify_organization(organization_id, body.verified)
    if result is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return result


@router.get("/alerts/{alert_id}/organizations", summary="Preview notification matches for an alert")
async def preview_notifications(alert_id: str):
    try:
        return await IntelligenceService.preview_notifications(alert_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/alerts/{alert_id}/notifications", summary="Approve and send an alert email")
async def send_notification(
    alert_id: str,
    body: NotificationApproval,
    current_user: User = Depends(require_admin_user),
):
    try:
        return await IntelligenceService.send_notification(
            alert_id,
            body.organization_id,
            current_user.user_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/alerts/{alert_id}/notifications", summary="List alert notification delivery records")
async def list_alert_notifications(alert_id: str):
    return await IntelligenceService.list_notifications(alert_id)


@router.patch("/notifications/{notification_id}/acknowledge", summary="Record an organization notification acknowledgment")
async def acknowledge_notification(
    notification_id: str,
    body: NotificationAcknowledgment,
    current_user: User = Depends(require_admin_user),
):
    result = await IntelligenceService.acknowledge_notification(
        notification_id,
        current_user.user_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Sent notification not found.")
    return result
