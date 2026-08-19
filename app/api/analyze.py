from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.core.logging import get_request_id
from app.core.security import require_api_key
from app.models.schemas import ImageAnalysisResponse, VideoAnalysisResponse
from app.services.image_analysis import analyze_image_bytes
from app.services.video_analysis import analyze_video_bytes

router = APIRouter(tags=["analyze"])

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}
VIDEO_TYPES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


@router.post("/analyze/image", response_model=ImageAnalysisResponse)
async def analyze_image(
    request: Request,
    file: UploadFile = File(...),
    question: str | None = Form(default=None),
    _: None = Depends(require_api_key),
) -> ImageAnalysisResponse:
    request_id = get_request_id(request)
    filename = file.filename or "image.jpg"
    suffix = filename.lower()[filename.rfind(".") :] if "." in filename else ""
    if suffix not in IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail={"request_id": request_id, "error": "unsupported_format", "detail": str(IMAGE_TYPES)},
        )
    file_bytes = await file.read()
    result = await analyze_image_bytes(file_bytes, filename, question=question)
    return ImageAnalysisResponse(request_id=request_id, result=result)


@router.post("/analyze/video", response_model=VideoAnalysisResponse)
async def analyze_video(
    request: Request,
    file: UploadFile = File(...),
    question: str | None = Form(default=None),
    _: None = Depends(require_api_key),
) -> VideoAnalysisResponse:
    request_id = get_request_id(request)
    filename = file.filename or "video.mp4"
    suffix = filename.lower()[filename.rfind(".") :] if "." in filename else ""
    if suffix not in VIDEO_TYPES:
        raise HTTPException(
            status_code=400,
            detail={"request_id": request_id, "error": "unsupported_format", "detail": str(VIDEO_TYPES)},
        )
    file_bytes = await file.read()
    result = await analyze_video_bytes(file_bytes, filename, question=question)
    return VideoAnalysisResponse(request_id=request_id, result=result)
