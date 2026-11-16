from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.auth import require_active_user
from app.schemas.satellite import HotspotCatalogItem, SatelliteAnalysisResponse, SatelliteValidationResponse
from app.services.satellite_service import (
    InvalidSatelliteRasterError,
    SatelliteService,
    SatelliteUnavailableError,
)

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_active_user)])
MAX_UPLOAD_BYTES = 512 * 1024 * 1024


@router.get("/catalog", response_model=List[HotspotCatalogItem], summary="Get pre-registered coastal monitoring sites")
@router.get("/hotspots", response_model=List[HotspotCatalogItem], summary="Get pre-registered coastal monitoring sites (alias)")
async def get_hotspot_catalog():
    """Returns the catalog of pre-registered coastal monitoring sites with Sentinel-2 sample imagery."""
    return SatelliteService.get_catalog()


@router.post("/analyze", response_model=SatelliteAnalysisResponse, summary="Analyze Sentinel-2 GeoTIFF or registered hotspot")
async def analyze_satellite(
    request: Request,
    file: Optional[UploadFile] = File(None, description="11-band Sentinel-2 L2A GeoTIFF file"),
    hotspot_id: Optional[str] = Form(None, description="Pre-registered hotspot ID if analyzing local sample"),
    provenance_manifest_json: Optional[str] = Form(None, description="Signed provenance manifest JSON"),
    site_id: Optional[str] = Form(None, description="Optional monitoring site for footprint validation"),
):
    """
    Analyzes an 11-band Sentinel-2 L2A GeoTIFF for marine debris using the MARIDA U-Net model.

    Supports two input sources:
    1. **Custom GeoTIFF upload**: Provide `file` as multipart form data.
    2. **Registered hotspot**: Provide `hotspot_id` (e.g. `accra-coast`, `gulf-of-honduras`, `durban-harbor`, `coastal-demo-site`)
       either as form data or in a JSON body.
    """
    # 1. Check if JSON payload was sent with hotspot_id
    if file is None and hotspot_id is None:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                body = await request.json()
                if isinstance(body, dict):
                    hotspot_id = body.get("hotspot_id")
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise HTTPException(status_code=422, detail="Request body must contain valid JSON.") from exc

    # 2. Case A: Uploaded GeoTIFF
    if file is not None:
        try:
            filename = file.filename or ""
            if Path(filename).suffix.lower() not in {".tif", ".tiff"}:
                raise HTTPException(status_code=422, detail="Upload must be a .tif or .tiff GeoTIFF file.")
            file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
            if len(file_bytes) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="GeoTIFF upload exceeds the 512 MB limit.")
            if not file_bytes:
                raise HTTPException(status_code=422, detail="Uploaded file is empty.")
            site = SatelliteService.CATALOG.get(site_id) if site_id else None
            if site_id and site is None:
                raise HTTPException(status_code=404, detail="Unknown monitoring site ID.")
            return await run_in_threadpool(
                SatelliteService.analyze_geotiff_bytes,
                file_bytes=file_bytes,
                site_name=file.filename,
                provenance_manifest_json=provenance_manifest_json,
                coordinates=site["coordinates"] if site else None,
            )
        except HTTPException:
            raise
        except InvalidSatelliteRasterError as exc:
            detail = exc.args[0] if exc.args and isinstance(exc.args[0], dict) else {"validation_errors": [str(exc)]}
            raise HTTPException(status_code=422, detail=detail) from exc
        except SatelliteUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected satellite inference error for uploaded file %r.", filename)
            raise HTTPException(status_code=500, detail="Satellite analysis failed. Check the backend logs for details.") from exc
        finally:
            await file.close()

    # 3. Case B: Registered Hotspot ID
    if hotspot_id:
        try:
            return await run_in_threadpool(SatelliteService.analyze_registered_hotspot, hotspot_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidSatelliteRasterError as exc:
            detail = exc.args[0] if exc.args and isinstance(exc.args[0], dict) else {"validation_errors": [str(exc)]}
            raise HTTPException(status_code=422, detail=detail) from exc
        except SatelliteUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected satellite inference error for hotspot %r.", hotspot_id)
            raise HTTPException(status_code=500, detail="Satellite analysis failed. Check the backend logs for details.") from exc

    # Neither provided
    raise HTTPException(
        status_code=422,
        detail="Please provide an 11-band Sentinel-2 GeoTIFF file or a registered hotspot_id."
    )


@router.post("/validate", response_model=SatelliteValidationResponse, summary="Validate a Sentinel-2 input before analysis")
async def validate_satellite_upload(
    file: UploadFile = File(..., description="GeoTIFF raster to validate"),
    provenance_manifest_json: Optional[str] = Form(None, description="Optional signed provenance manifest JSON"),
    site_id: Optional[str] = Form(None, description="Optional registered site to check coverage against"),
):
    filename = file.filename or ""
    try:
        if Path(filename).suffix.lower() not in {".tif", ".tiff"}:
            raise HTTPException(status_code=422, detail="Upload must be a .tif or .tiff GeoTIFF file.")
        file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="GeoTIFF upload exceeds the 512 MB limit.")
        site = SatelliteService.CATALOG.get(site_id) if site_id else None
        if site_id and site is None:
            raise HTTPException(status_code=404, detail="Unknown monitoring site ID.")
        return await run_in_threadpool(
            SatelliteService.validate_geotiff_bytes,
            file_bytes,
            provenance_manifest_json,
            site["coordinates"] if site else None,
        )
    finally:
        await file.close()


@router.post("/hotspots/{hotspot_id}/analyze", response_model=SatelliteAnalysisResponse, summary="Analyze pre-registered hotspot by ID")
@router.get("/hotspots/{hotspot_id}/analyze", response_model=SatelliteAnalysisResponse, summary="Analyze pre-registered hotspot by ID (GET)")
async def analyze_hotspot_by_id(hotspot_id: str):
    """Convenience endpoint to analyze a pre-registered coastal monitoring site by its ID."""
    try:
        return await run_in_threadpool(SatelliteService.analyze_registered_hotspot, hotspot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidSatelliteRasterError as exc:
        detail = exc.args[0] if exc.args and isinstance(exc.args[0], dict) else {"validation_errors": [str(exc)]}
        raise HTTPException(status_code=422, detail=detail) from exc
    except SatelliteUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected satellite inference error for hotspot %r.", hotspot_id)
        raise HTTPException(status_code=500, detail="Satellite analysis failed. Check the backend logs for details.") from exc
