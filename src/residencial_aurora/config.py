"""Configuração central da aplicação."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

MODEL_NAME = "gemini-3.1-flash-lite"


@dataclass(frozen=True)
class Settings:
    google_api_key: str | None = os.getenv("GOOGLE_API_KEY")
    database_path: Path = Path(
        os.getenv("DATABASE_PATH") or str(PROJECT_ROOT / "data" / "residencial_aurora.sqlite3")
    )


settings = Settings()
