import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env files (both chatbot and backend)
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / "backend" / ".env")

# Settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
BACKEND_API_BASE = os.getenv("BACKEND_API_BASE", "http://127.0.0.1:8000")
VERIFICATION_API_URL = os.getenv("VERIFICATION_API_URL", f"{BACKEND_API_BASE}/cases")
BOT_USER_EMAIL = os.getenv("BOT_USER_EMAIL", "telegram.citizen@docsure.internal")
BOT_USER_PASSWORD = os.getenv("BOT_USER_PASSWORD", "DocSureCitizenPass123!")
MOCK_MODE = False  # Strictly 100% real analysis, zero mock data

# Temp storage for incoming citizen document photos
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)
