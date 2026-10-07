"""
Post-generation claim verification.

For each [chunk_N] citation in the LLM's answer, a second (cheap,
deterministic) LLM call checks whether the cited chunk text actually
supports the claim it accompanies.  Unsupported claims are stripped.
"""

import re

from app.generation.llm_client import LLMClient
from app.generation.prompt_templates import (
    CITATION_RE,
    build_verifier_messages,
    parse_llm_response,
)


def verify_answer(
    answer: str,
    chunks: list[dict],
    client: LLMClient,
    max_tokens: int = 2000,
) -> tuple[str, list[dict]]:
    """Run the verification pass.

    Parameters
    ----------
    answer
        The raw answer text produced by the generation step (may contain
        [chunk_N] citations).
    chunks
        All chunks that were provided to the generator.
    client
        An LLMClient instance for the verification call.

    Returns
    -------
    (cleaned_answer, verified_chunks)
        *cleaned_answer* has unsupported claims removed.
        *verified_chunks* is the subset of *chunks* whose citations
        survived verification.
    """
    # Extract chunk IDs cited in the answer
    cited_ids = {int(m) for m in CITATION_RE.findall(answer)}
    if not cited_ids:
        return answer, []

    # Build a quick lookup so we can grab just the cited chunks
    chunk_map = {c["chunk_id"]: c for c in chunks}
    cited_chunks = [
        chunk_map[cid] for cid in cited_ids if cid in chunk_map
    ]

    # Ask the verifier LLM to re-write the answer, dropping unsupported claims
    messages = build_verifier_messages(answer, cited_chunks)
    raw_response = client.generate(messages, temperature=0.0, max_tokens=max_tokens)

    cleaned_answer, verified_ids = parse_llm_response(raw_response)

    # If the verifier returned nothing usable, fall back to the original
    if not cleaned_answer:
        cleaned_answer = answer
        verified_ids = list(cited_ids)

    verified_chunks = [
        chunk_map[i] for i in verified_ids if i in chunk_map
    ]

    return cleaned_answer, verified_chunks
