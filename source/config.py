"""Settings read from the environment (.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")
load_dotenv()

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai").lower()
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4.1-mini")
API_KEY = os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
WORKERS = int(os.getenv("WORKERS", "4"))
EXAMPLE_DIR = BASE / "examples"

# Used only in --dev mode (training bills have no question template).
DEV_QUESTIONS = [
    ("Q1", "How much of my bill is taxes?"),
    ("Q2", "How many months in my history went above 200 units?"),
    ("Q3", "How much will I pay if I miss the due date?"),
]
