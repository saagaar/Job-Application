from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.schemas import CVUploadResponse, CVContentResponse
from services import cv_service

router = APIRouter(prefix="/cv", tags=["cv"])

_ACCEPTED = {".pdf", ".docx"}
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("", response_model=CVUploadResponse, summary="Upload master CV (PDF or DOCX)")
async def upload_cv(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ACCEPTED:
        raise HTTPException(status_code=400, detail="Only .pdf and .docx files are accepted.")

    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit.")

    try:
        result = cv_service.process_upload(data, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return result


@router.get("", response_model=CVContentResponse, summary="Get current master CV as Markdown")
def get_cv():
    content = cv_service.get_cv_content()
    if not content.strip():
        raise HTTPException(status_code=404, detail="No CV uploaded yet.")
    return {"content": content, "chars": len(content)}
