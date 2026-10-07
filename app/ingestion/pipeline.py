"""
Pipeline: extract → chunk → embed → insert.

Three entry-points plus a CSV processor cover the source types required
by the demo:
    process_pdf        – native-text PDF  (PyMuPDF)
    process_image      – scanned image    (pytesseract + Pillow)
    process_db_records – structured rows  (db_templater)
    process_csv        – generic CSV      (row → sentence)

All entry-points return the list of new chunk_ids so callers can
reference exact rows.
"""

import csv
import json
import os

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ingestion.pdf_extractor import extract_pdf
from app.ingestion.ocr_extractor import extract_image
from app.ingestion.db_templater import row_to_sentence
from app.ingestion.chunker import chunk_text
from app.ingestion.embedder import Embedder

_INSERT_SQL = text("""
    INSERT INTO chunks
        (source_doc_id, source_type, raw_text, exact_locator,
         embedding, tenant_id, allowed_principals)
    VALUES
        (:source_doc_id, :source_type, :raw_text, :exact_locator,
         CAST(:embedding AS vector(384)), :tenant_id, :allowed_principals)
    RETURNING chunk_id
""")


def _embedding_str(embedding: np.ndarray) -> str:
    vals = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
    return "[" + ", ".join(f"{v:.8f}" for v in vals) + "]"


def insert_chunks(chunks: list[dict], db: Session) -> list[int]:
    """Insert chunk dicts into the chunks table; return their chunk_ids."""
    if not chunks:
        return []

    chunk_ids: list[int] = []
    for chunk in chunks:
        params = {
            "source_doc_id": chunk["source_doc_id"],
            "source_type": chunk["source_type"],
            "raw_text": chunk["raw_text"],
            "exact_locator": json.dumps(chunk["exact_locator"]),
            "embedding": _embedding_str(chunk["embedding"]),
            "tenant_id": chunk["tenant_id"],
            "allowed_principals": chunk["allowed_principals"],
        }
        result = db.execute(_INSERT_SQL, params)
        chunk_ids.append(result.fetchone()[0])

    return chunk_ids


def _chunk_and_embed(
    segments: list[dict],
    source_type: str,
    source_doc_id: str,
    default_tenant_id: int,
    default_allowed_principals: list[str],
) -> list[dict]:
    """Turn segments into chunk dicts with embeddings."""
    embedder = Embedder()
    chunks: list[dict] = []

    for seg in segments:
        texts = chunk_text(seg["text"])
        if not texts:
            continue

        embeddings = embedder.embed(texts)
        for i, t in enumerate(texts):
            row = seg.get("_row")
            chunks.append(
                {
                    "source_doc_id": source_doc_id,
                    "source_type": source_type,
                    "raw_text": t,
                    "exact_locator": seg["exact_locator"],
                    "embedding": embeddings[i],
                    "tenant_id": row.get("tenant_id", default_tenant_id)
                    if row
                    else default_tenant_id,
                    "allowed_principals": row.get("allowed_principals", default_allowed_principals)
                    if row
                    else default_allowed_principals,
                }
            )

    return chunks


# ─── Public entry-points ──────────────────────────────────────────────


def process_pdf(
    path: str,
    tenant_id: int,
    allowed_principals: list[str],
    source_doc_id: str,
    db: Session,
) -> list[int]:
    """Extract text from a PDF, chunk, embed, and store."""
    segments = extract_pdf(path)
    chunks = _chunk_and_embed(
        segments, "pdf", source_doc_id, tenant_id, allowed_principals
    )
    return insert_chunks(chunks, db)


def process_image(
    path: str,
    tenant_id: int,
    allowed_principals: list[str],
    source_doc_id: str,
    db: Session,
) -> list[int]:
    """OCR an image, chunk, embed, and store."""
    segments = extract_image(path)
    chunks = _chunk_and_embed(
        segments, "ocr", source_doc_id, tenant_id, allowed_principals
    )
    return insert_chunks(chunks, db)


def process_db_records(
    rows: list[dict],
    source_doc_id: str,
    db: Session,
) -> list[int]:
    """Convert structured DB rows to text chunks, embed, and store.

    Each row carries its own allowed_principals so different rows can
    have different visibility (e.g. salary rows = finance-only,
    performance-review rows = hr-only).
    """
    embedder = Embedder()
    chunks: list[dict] = []

    for row in rows:
        sentence = row_to_sentence(row)
        texts = chunk_text(sentence)
        if not texts:
            continue

        embeddings = embedder.embed(texts)
        for i, t in enumerate(texts):
            chunks.append(
                {
                    "source_doc_id": source_doc_id,
                    "source_type": "db",
                    "raw_text": t,
                    "exact_locator": {
                        "source": "db",
                        "table": "employee_records",
                        "row_id": row.get("record_id"),
                        "field_name": row.get("field_name"),
                    },
                    "embedding": embeddings[i],
                    "tenant_id": row.get("tenant_id", 1),
                    "allowed_principals": row.get("allowed_principals", []),
                }
            )

    return insert_chunks(chunks, db)


def process_csv(
    path: str,
    tenant_id: int,
    allowed_principals: list[str],
    source_doc_id: str,
    db: Session,
) -> list[int]:
    """Parse a CSV file, convert rows to sentences, chunk, embed, insert."""
    segments: list[dict] = []
    basename = os.path.basename(path)
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if "employee_name" in row and "field_name" in row and "field_value" in row:
                sentence = row_to_sentence(row)
            else:
                parts = [f"{k}: {v}" for k, v in row.items() if v]
                sentence = " ".join(parts)
            segments.append(
                {
                    "text": sentence,
                    "source_type": "csv",
                    "exact_locator": {
                        "source": "csv",
                        "file": basename,
                        "row": i + 2,
                    },
                }
            )

    chunks = _chunk_and_embed(
        segments, "csv", source_doc_id, tenant_id, allowed_principals
    )
    return insert_chunks(chunks, db)


def read_employee_records(db: Session, tenant_id: int = 1) -> list[dict]:
    """Read all employee_records visible to the current session context."""
    result = db.execute(
        text(
            """
            SELECT record_id, employee_name, field_name, field_value,
                   raw_text, exact_locator, tenant_id, allowed_principals
            FROM employee_records
            WHERE tenant_id = :tid
            ORDER BY record_id
            """
        ),
        {"tid": tenant_id},
    )
    return [dict(row._mapping) for row in result]


def insert_employee_records(records: list[dict], db: Session) -> list[int]:
    """Insert raw employee_records rows. Returns their record_ids.

    Unlike chunks, these rows are not restricted by RLS on INSERT
    (policies are USING-only).  The caller is responsible for setting
    admin context so subsequent reads see all rows.
    """
    stmt = text(
        """
        INSERT INTO employee_records
            (source_doc_id, raw_text, exact_locator, tenant_id,
             allowed_principals, employee_name, field_name, field_value)
        VALUES
            (:source_doc_id, :raw_text, :exact_locator, :tenant_id,
             :allowed_principals, :employee_name, :field_name, :field_value)
        RETURNING record_id
        """
    )

    record_ids: list[int] = []
    for rec in records:
        params = {
            "source_doc_id": rec.get("source_doc_id", "employee_records"),
            "raw_text": rec.get("raw_text", ""),
            "exact_locator": json.dumps(rec.get("exact_locator", {})),
            "tenant_id": rec.get("tenant_id", 1),
            "allowed_principals": rec.get("allowed_principals", []),
            "employee_name": rec.get("employee_name"),
            "field_name": rec.get("field_name"),
            "field_value": rec.get("field_value"),
        }
        result = db.execute(stmt, params)
        record_ids.append(result.fetchone()[0])

    return record_ids
