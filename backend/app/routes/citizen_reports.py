from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.core.auth import require_active_user, require_admin_user
from app.models.user import User
from app.schemas.cleanup import CitizenReportCategory, CitizenReportModeration
from app.services.citizen_report_service import CitizenReportService
from app.services.private_media import PrivateMediaError


router = APIRouter(dependencies=[Depends(require_active_user)])


@router.post("", status_code=201, summary="Submit an unverified citizen pollution report")
async def submit_report(
    category: CitizenReportCategory = Form(...),
    description: str = Form(..., min_length=10, max_length=4000),
    latitude: float = Form(..., ge=-90, le=90),
    longitude: float = Form(..., ge=-180, le=180),
    observed_at: datetime = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_active_user),
):
    try:
        return await CitizenReportService.submit(
            category=category,
            description=description,
            latitude=latitude,
            longitude=longitude,
            observed_at=observed_at,
            upload=file,
            user_id=current_user.user_id,
        )
    except PrivateMediaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()


@router.get("", summary="List own citizen reports or all reports for administrators")
async def list_reports(
    status: Optional[str] = Query(None, pattern="^(PENDING|UNDER_REVIEW|VERIFIED|REJECTED)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(require_active_user),
):
    return await CitizenReportService.list_reports(
        user_id=current_user.user_id,
        is_admin=current_user.is_admin,
        status=status,
        skip=skip,
        limit=limit,
    )


@router.patch("/{report_id}/moderation", summary="Moderate a citizen report")
async def moderate_report(
    report_id: str,
    body: CitizenReportModeration,
    current_user: User = Depends(require_admin_user),
):
    try:
        result = await CitizenReportService.moderate(
            report_id, body.status, body.reason, current_user.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Citizen report not found.")
    return result


@router.get("/{report_id}/photo", summary="Download a protected citizen report photograph")
async def get_report_photo(
    report_id: str,
    current_user: User = Depends(require_active_user),
):
    media = await CitizenReportService.get_photo(
        report_id, current_user.user_id, current_user.is_admin
    )
    if media is None or not media["path"].is_file():
        raise HTTPException(status_code=404, detail="Citizen report photograph not found.")
    return FileResponse(
        media["path"],
        media_type=media["content_type"],
        filename=f"citizen-report-{report_id}.{media['extension']}",
        headers={"Cache-Control": "private, no-store"},
    )
