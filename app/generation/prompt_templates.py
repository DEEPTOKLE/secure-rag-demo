"""
Prompt templates for RAG generation and claim verification.

Key design: the LLM is told (a) to answer ONLY from the provided chunks,
(b) to cite each chunk with [chunk_N], and (c) to say
"not found in your accessible documents" when the authorised context
does not cover a part of the question.
"""

SYSTEM_PROMPT = """\
You are a retrieval-augmented assistant. Answer questions using ONLY the \
text from the provided chunks. Each chunk is labelled [chunk_N].

Rules:
1. Answer ONLY from the provided chunks. Never use your own background knowledge.
2. For every factual claim, cite the chunk with [chunk_N] immediately after the claim.
3. If part of the question cannot be answered from the available chunks, say: \
"not found in your accessible documents."
4. Keep your answer concise but complete.

Output format:
ANSWER: <answer with inline [chunk_N] citations>
CITATIONS: <space-separated list of chunk ids used, e.g. chunk_5 chunk_3>
"""

VERIFY_SYSTEM_PROMPT = """\
You are a fact checker. Below is an AI-generated answer that cites chunks \
using [chunk_N] notation, along with the text of each cited chunk.

For each [chunk_N] in the answer, check whether the cited chunk's text \
**actually supports** the claim it accompanies. If it does, mark \
SUPPORTED. If the chunk text does not support the claim, mark \
UNSUPPORTED – the claim will be dropped.

Leave "not found in your accessible documents" phrases unchanged.

Rewrite the answer keeping only supported claims and their citations.

Output format (exact):
ANSWER: <cleaned answer with only supported claims and [chunk_N] citations>
CITATIONS: <space-separated list of *verified* chunk ids, e.g. chunk_5 chunk_3>
"""

# Regex to find [chunk_N] citations in the answer
import re

CITATION_RE = re.compile(r"\[chunk_(\d+)\]")


def build_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into a context block for the prompt."""
    parts = []
    for c in chunks:
        locator_info = ""
        if c.get("exact_locator"):
            loc = c["exact_locator"]
            if loc.get("source") == "pdf":
                locator_info = f" (page {loc.get('page', '?')})"
            elif loc.get("source") == "ocr":
                locator_info = f" (region {loc.get('region', {})})"
            elif loc.get("source") == "db":
                locator_info = f" (table {loc.get('table', '?')}, row {loc.get('row_id', '?')}, col {loc.get('field_name', '?')})"
        parts.append(
            f"[chunk_{c['chunk_id']}] (source: {c.get('source_type', 'unknown')})"
            f"{locator_info}\n{c['raw_text']}"
        )
    return "\n\n".join(parts)


def build_generate_messages(question: str, chunks: list[dict]) -> list[dict[str, str]]:
    """Build the message list for the answer-generation LLM call."""
    context = build_context(chunks)
    user_msg = f"""\
Question: {question}

Retrieved context:
{context}
"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


def build_verifier_messages(answer: str, cited_chunks: list[dict]) -> list[dict[str, str]]:
    """Build the message list for the claim-verification LLM call."""
    chunk_texts = "\n\n".join(
        f"[chunk_{c['chunk_id']}]\n{c['raw_text']}" for c in cited_chunks
    )
    user_msg = f"""\
ANSWER: {answer}

CITED CHUNK TEXTS:
{chunk_texts}
"""
    return [
        {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


def parse_llm_response(text: str) -> tuple[str, list[int]]:
    """Parse the LLM response into (answer, cited_chunk_ids)."""
    answer = ""
    chunk_ids: list[int] = []

    for line in text.strip().split("\n"):
        if line.startswith("ANSWER:"):
            answer = line[len("ANSWER:"):].strip()
        elif line.startswith("CITATIONS:"):
            ids_str = line[len("CITATIONS:"):].strip()
            for tok in ids_str.split():
                if tok.startswith("chunk_"):
                    try:
                        chunk_ids.append(int(tok[len("chunk_"):]))
                    except ValueError:
                        pass

    # Fallback: if no CITATIONS line, extract from inline [chunk_N] notation
    if not chunk_ids:
        chunk_ids = [int(m) for m in CITATION_RE.findall(answer)]

    return answer, chunk_ids
