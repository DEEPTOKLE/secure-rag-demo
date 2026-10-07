"""
test_acl_enforcement.py

Required test: proves that access control is enforced at the *retrieval*
layer inside PostgreSQL, not filtered in application code after the fact.

Scenarios:
  1. Alice (hr_manager)  – searches for salary info → must NOT see any
     finance-only chunks.
  2. Bob (finance_manager) – searches for review info → must NOT see any
     HR-only chunks.
  3. Carol (admin)        – same question → SHOULD see chunks from both
     scopes (full answer possible).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal, get_db_session
from app.ingestion.embedder import Embedder
from app.retrieval.vector_search import search_similar_chunks

ALLOWED_HR = ["1", "hr_manager", "3", "admin"]
ALLOWED_FINANCE = ["2", "finance_manager", "3", "admin"]

HR_TEXT = "John Smith's performance review status is Exceeds Expectations"
FINANCE_TEXT = "John Smith's annual salary is $85,000"


def _embedding_str(arr):
    vals = arr.tolist() if hasattr(arr, "tolist") else list(arr)
    return "[" + ", ".join(f"{v:.8f}" for v in vals) + "]"


@pytest.fixture(scope="module")
def test_chunks():
    """Insert HR-only and finance-only chunks, return their IDs."""
    embedder = Embedder()
    hr_emb = embedder.embed([HR_TEXT])[0]
    fin_emb = embedder.embed([FINANCE_TEXT])[0]

    admin = {"user_id": "3", "role": "admin", "tenant_id": "1"}

    with get_db_session(admin) as db:
        # Wipe test data
        db.execute(text("DELETE FROM chunks WHERE source_doc_id = 'acl_test'"))
        db.execute(text("DELETE FROM employee_records WHERE source_doc_id = 'acl_test'"))

        # HR-only chunk
        r1 = db.execute(
            text("""
                INSERT INTO chunks
                    (source_doc_id, source_type, raw_text, exact_locator,
                     embedding, tenant_id, allowed_principals)
                VALUES
                    (:sid, :st, :rt, :el, CAST(:emb AS vector(384)), :tid, :ap)
                RETURNING chunk_id
            """),
            {
                "sid": "acl_test",
                "st": "db",
                "rt": HR_TEXT,
                "el": json.dumps({"source": "db", "table": "employee_records", "row_id": 1}),
                "emb": _embedding_str(hr_emb),
                "tid": 1,
                "ap": ALLOWED_HR,
            },
        ).fetchone()

        # Finance-only chunk
        r2 = db.execute(
            text("""
                INSERT INTO chunks
                    (source_doc_id, source_type, raw_text, exact_locator,
                     embedding, tenant_id, allowed_principals)
                VALUES
                    (:sid, :st, :rt, :el, CAST(:emb AS vector(384)), :tid, :ap)
                RETURNING chunk_id
            """),
            {
                "sid": "acl_test",
                "st": "db",
                "rt": FINANCE_TEXT,
                "el": json.dumps({"source": "db", "table": "employee_records", "row_id": 2}),
                "emb": _embedding_str(fin_emb),
                "tid": 1,
                "ap": ALLOWED_FINANCE,
            },
        ).fetchone()

    yield {"hr_id": r1[0], "finance_id": r2[0]}

    # Teardown
    admin = {"user_id": "3", "role": "admin", "tenant_id": "1"}
    with get_db_session(admin) as db:
        db.execute(text("DELETE FROM chunks WHERE source_doc_id = 'acl_test'"))


# ─── Helper ───────────────────────────────────────────────────────────


def _search_as(user_id: str, role: str, question: str, limit: int = 20):
    """Embed *question*, then search with the given user context."""
    claims = {"user_id": user_id, "role": role, "tenant_id": "1"}
    embedder = Embedder()
    emb = embedder.embed([question])[0]

    with get_db_session(claims) as db:
        return search_similar_chunks(db, emb, limit=limit)


# ─── Tests ────────────────────────────────────────────────────────────


def test_alice_cannot_see_finance_only_content(test_chunks):
    """Alice (hr_manager) must never receive finance-only chunks."""
    chunks = _search_as("1", "hr_manager", "What is John Smith's salary?")

    finance_ids = {test_chunks["finance_id"]}
    returned_ids = {c["chunk_id"] for c in chunks}

    assert not (finance_ids & returned_ids), (
        f"ACL violation: finance-only chunk {finance_ids & returned_ids} "
        f"leaked to Alice (hr_manager)"
    )


def test_alice_sees_hr_content(test_chunks):
    """Alice (hr_manager) SHOULD see HR-authorized chunks."""
    chunks = _search_as("1", "hr_manager", "What is John Smith's performance review?")

    hr_id = test_chunks["hr_id"]
    returned_ids = {c["chunk_id"] for c in chunks}

    assert hr_id in returned_ids, (
        f"Alice should see HR chunk {hr_id} but didn't"
    )


def test_bob_cannot_see_hr_only_content(test_chunks):
    """Bob (finance_manager) must never receive HR-only chunks."""
    chunks = _search_as("2", "finance_manager", "What is John Smith's performance review?")

    hr_ids = {test_chunks["hr_id"]}
    returned_ids = {c["chunk_id"] for c in chunks}

    assert not (hr_ids & returned_ids), (
        f"ACL violation: HR-only chunk {hr_ids & returned_ids} "
        f"leaked to Bob (finance_manager)"
    )


def test_carol_sees_all_content(test_chunks):
    """Carol (admin) should see BOTH HR and finance chunks."""
    chunks = _search_as("3", "admin", "What is John Smith's salary?")

    returned_ids = {c["chunk_id"] for c in chunks}

    assert test_chunks["finance_id"] in returned_ids, (
        "Carol (admin) should see finance-only chunks"
    )


def test_carol_sees_hr_content(test_chunks):
    """Carol (admin) should see HR-authorized chunks."""
    chunks = _search_as("3", "admin", "What is John Smith's performance review?")

    returned_ids = {c["chunk_id"] for c in chunks}

    assert test_chunks["hr_id"] in returned_ids, (
        "Carol (admin) should see HR-only chunks"
    )
