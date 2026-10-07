"""
Provider-agnostic LLM client.

Wraps the OpenAI-compatible chat-completion API so the underlying model
or vendor can be swapped by changing LLM_BASE_URL / LLM_MODEL in the
environment – no other code needs to change.
"""

from openai import OpenAI

from app.config import GEMINI_API_KEY, LLM_BASE_URL, LLM_MODEL


class LLMClient:
    """Thin wrapper around OpenAI-compatible chat completions."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.base_url = base_url or LLM_BASE_URL
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or LLM_MODEL
        if not self.api_key:
            raise RuntimeError(
                "No LLM_API_KEY configured. Set GEMINI_API_KEY in the environment."
            )
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        """Send messages and return the assistant's text response."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content


_default_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Module-level singleton so the model/encoder is loaded once."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client
