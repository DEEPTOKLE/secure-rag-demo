"""
POST /query – authenticated retrieval + generation + verification.

Flow:
    1. Embed the question (local sentence-transformers)
    2. Run the single fused vector+ACL SQL query (pgvector HNSW)
    3. Generate an answer citing [chunk_N] (Gemini 2.0 Flash)
    4. Verify each citation with a second LLM pass (verifier)
    5. Return the cleaned answer and verified citations
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ingestion.embedder import Embedder
from app.retrieval.vector_search import search_similar_chunks
from app.generation.llm_client import LLMClient, get_llm_client
from app.generation.prompt_templates import (
    build_generate_messages,
    parse_llm_response,
)
from app.generation.verifier import verify_answer

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    question: str


class Citation(BaseModel):
    chunk_id: int
    source_type: str
    exact_locator: dict | None = None
    snippet: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]


@router.post("/", response_model=QueryResponse)
async def query(payload: QueryRequest, db: Session = Depends(get_db)):
    if not payload.question.strip():
        raise HTTPException(400, "Question must not be empty")

    # 1. Embed the question
    embedder = Embedder()
    query_embedding = embedder.embed([payload.question])[0]

    # 2. Fused vector + ACL search (single SQL query, no post-hoc filtering)
    chunks = search_similar_chunks(db, query_embedding, limit=10)

    if not chunks:
        return QueryResponse(
            answer="not found in your accessible documents",
            citations=[],
        )

    # 3-4. Generate answer with citations and verify claims
    # If no valid LLM_API_KEY is configured, fall back to returning the
    # access-controlled chunks so the retrieval-layer ACL is still observable.
    try:
        llm: LLMClient = get_llm_client()
        messages = build_generate_messages(payload.question, chunks)
        raw_response = llm.generate(messages)
        answer, cited_ids = parse_llm_response(raw_response)
        cleaned_answer, verified_chunks = verify_answer(answer, chunks, llm)
    except Exception:
        cleaned_answer = (
            "LLM generation unavailable. Below are the access-controlled "
            "chunks retrieved by your query (ACL enforced in PostgreSQL):"
        )
        verified_chunks = chunks

    # 5. Build response
    citations: list[Citation] = []
    for c in verified_chunks:
        citations.append(
            Citation(
                chunk_id=c["chunk_id"],
                source_type=c.get("source_type", "unknown"),
                exact_locator=c.get("exact_locator"),
                snippet=(c["raw_text"][:200] if len(c["raw_text"]) > 200 else c["raw_text"]),
            )
        )

    # If verification removed all citations, the answer should reflect that
    if not citations:
        cleaned_answer = "not found in your accessible documents"

    return QueryResponse(answer=cleaned_answer, citations=citations)
