"""
POST /ingest – admin-only document ingestion.

Accepts PDF, image (PNG/JPG/etc.), or CSV files.  Runs the full pipeline
(extract → chunk → embed → insert) under the admin's session so the
app.* ACL variables are always set inside a real transaction.
"""

import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role
from app.db.session import get_db
from app.ingestion.pipeline import process_pdf, process_image, process_csv

router = APIRouter(prefix="/ingest", tags=["ingest"])

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
_PDF_EXTS = {".pdf"}
_CSV_EXTS = {".csv", ".tsv"}


def _detect_source_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in _PDF_EXTS:
        return "pdf"
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _CSV_EXTS:
        return "csv"
    raise HTTPException(
        status_code=400,
        detail=f"Unsupported file type: {ext}. Supported: PDF, images, CSV.",
    )


@router.post("/")
async def ingest_file(
    file: UploadFile = File(...),
    allowed_principals_str: str = Form(default=""),
    admin: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Upload and process a document (PDF / image / CSV).

    *allowed_principals* is a comma-separated list of user IDs or roles
    that may see the ingested chunks.  If omitted, only the uploading
    admin can see the content.
    """
    source_doc_id = os.path.splitext(file.filename)[0]
    src_type = _detect_source_type(file.filename)

    if allowed_principals_str.strip():
        allowed_principals = [
            p.strip() for p in allowed_principals_str.split(",") if p.strip()
        ]
    else:
        allowed_principals = [str(admin["user_id"]), admin["role"]]

    tenant_id = int(admin["tenant_id"])

    # Persist upload to a temp file
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if src_type == "pdf":
            chunk_ids = process_pdf(
                tmp_path, tenant_id, allowed_principals, source_doc_id, db
            )
        elif src_type == "image":
            chunk_ids = process_image(
                tmp_path, tenant_id, allowed_principals, source_doc_id, db
            )
        elif src_type == "csv":
            chunk_ids = process_csv(
                tmp_path, tenant_id, allowed_principals, source_doc_id, db
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported source type")
    finally:
        os.unlink(tmp_path)

    return {
        "message": f"Ingested {file.filename} successfully",
        "source_doc_id": source_doc_id,
        "chunk_count": len(chunk_ids),
        "chunk_ids": chunk_ids,
    }
