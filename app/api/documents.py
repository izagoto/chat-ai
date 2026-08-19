import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.core.config import settings
from app.core.logging import get_request_id
from app.core.owners import collection_id_for_request
from app.core.security import require_api_key
from app.models.schemas import (
    DocumentListResponse,
    DocumentRecordItem,
    DocumentUploadResponse,
    UrlIngestRequest,
)
from app.services.document_store import document_store
from app.services.ingest import IMAGE_EXTENSIONS, guessed_artifact_type
from app.services.ingest_queue import ingest_worker

router = APIRouter(tags=["documents"])

DOCUMENT_EXTENSIONS = {
    ".txt",
    ".md",
    ".log",
    ".json",
    ".csv",
    ".pdf",
    ".docx",
    ".xlsx",
    ".xls",
} | IMAGE_EXTENSIONS


@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    collection_id: str | None = Form(default=None),
    _: None = Depends(require_api_key),
) -> DocumentUploadResponse:
    request_id = get_request_id(request)
    filename = file.filename or "unknown"
    suffix = filename.lower()[filename.rfind(".") :] if "." in filename else ""
    if suffix not in DOCUMENT_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "request_id": request_id,
                "error": "unsupported_format",
                "detail": f"Supported: {', '.join(sorted(DOCUMENT_EXTENSIONS))}",
            },
        )

    coll = collection_id_for_request(request, collection_id)
    document_id = str(uuid.uuid4())[:12]
    file_bytes = await file.read()
    if len(file_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={
                "request_id": request_id,
                "error": "file_too_large",
                "detail": f"Max upload size is {settings.max_upload_bytes} bytes",
            },
        )

    record = document_store.stage_upload(
        coll, document_id, filename, file_bytes, guessed_artifact_type(filename)
    )
    await ingest_worker.submit(coll, document_id)
    latest = document_store.get_document(coll, document_id) or record
    return DocumentUploadResponse(
        request_id=request_id,
        collection_id=coll,
        document=DocumentRecordItem(**latest.__dict__),
    )


@router.post("/urls", response_model=DocumentUploadResponse)
async def ingest_url(
    body: UrlIngestRequest,
    request: Request,
    _: None = Depends(require_api_key),
) -> DocumentUploadResponse:
    request_id = get_request_id(request)
    from app.services.url_fetch import UrlFetchError, filename_for_url, validate_url

    try:
        url = validate_url(body.url)
    except UrlFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"request_id": request_id, "error": "url_blocked", "detail": str(exc)},
        ) from exc

    coll = collection_id_for_request(request, None)
    document_id = str(uuid.uuid4())[:12]
    filename = filename_for_url(url)
    record = document_store.stage_upload(
        coll,
        document_id,
        filename,
        url.encode("utf-8"),
        "url",
        source_url=url,
    )
    await ingest_worker.submit(coll, document_id)
    latest = document_store.get_document(coll, document_id) or record
    return DocumentUploadResponse(
        request_id=request_id,
        collection_id=coll,
        document=DocumentRecordItem(**latest.__dict__),
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    request: Request,
    collection_id: str | None = None,
    _: None = Depends(require_api_key),
) -> DocumentListResponse:
    request_id = get_request_id(request)
    coll = collection_id_for_request(request, collection_id)
    records = document_store.list_documents(coll)
    chunks = document_store.list_chunks(coll)
    return DocumentListResponse(
        request_id=request_id,
        collection_id=coll,
        documents=[DocumentRecordItem(**r.__dict__) for r in records],
        total_chunks=len(chunks),
    )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    request: Request,
    collection_id: str | None = None,
    _: None = Depends(require_api_key),
) -> dict:
    request_id = get_request_id(request)
    coll = collection_id_for_request(request, collection_id)
    ok = document_store.delete_document(coll, document_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"request_id": request_id, "error": "not_found", "detail": "Document not found"},
        )
    return {"request_id": request_id, "deleted": True, "document_id": document_id, "collection_id": coll}
