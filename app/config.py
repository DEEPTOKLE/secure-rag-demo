import os
import sys
from dotenv import load_dotenv

load_dotenv()


def _get_tesseract_cmd() -> str:
    env_val = os.environ.get("TESSERACT_CMD", "").strip()
    if env_val:
        return env_val
    if sys.platform == "win32":
        default_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(default_path):
            return default_path
    return "tesseract"


DATABASE_URL: str = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/securerag"
)
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
LLM_BASE_URL: str = os.environ.get(
    "LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
)
LLM_MODEL: str = os.environ.get("LLM_MODEL", "gemini-2.0-flash")
JWT_SECRET: str = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_MINUTES: int = int(
    os.environ.get("JWT_EXPIRATION_MINUTES", "1440")
)
TESSERACT_CMD: str = _get_tesseract_cmd()
EMBEDDING_MODEL: str = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
