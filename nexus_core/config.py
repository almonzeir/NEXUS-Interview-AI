
# ═════════════════════════════════════════════════════════════════════════
# NEXUS: AUTOMATED COMPETENCY ASSESSMENT SYSTEM (ACAS)
# Research Configuration & Constants
# ═════════════════════════════════════════════════════════════════════════

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ── SYSTEM PATHS ──
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "research_data"
SESSIONS_DIR = DATA_DIR / "sessions"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
REPORTS_DIR = DATA_DIR / "reports"

# Ensure directories exist
for d in [DATA_DIR, SESSIONS_DIR, TRANSCRIPTS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── API CONFIGURATION ──
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("CRITICAL ERROR: GROQ_API_KEY environment variable not set.")

# ── MODEL SELECTION (Methodology) ──
# Primary Model: Llama 3.3 70B (Production-grade, highest reasoning capability)
LLM_MODEL = "llama-3.3-70b-versatile"
LLM_TEMP = 0.6  # Balanced for creativity vs adherence to rubric
LLM_MAX_TOKENS = 4096

# Speech Models
STT_MODEL = "whisper-large-v3"       # OpenAI Whisper (State of the art open source)
TTS_VOICE = "en-US-GuyNeural"        # Microsoft Edge TTS (Professional male)
TTS_RATE = "+10%"                    # Slightly faster for natural flow

# ── SCORING RUBRIC (Research Instrument) ──
SCORING_DIMENSIONS = {
    "relevance": "Directness in answering the specific question asked.",
    "depth": "Presence of concrete examples, STAR method, and quantitative impact.",
    "competency": "Demonstration of the specific skill/domain expertise required.",
    "communication": "Clarity, structure, and professional delivery."
}

# ── INTERVIEW PROTOCOL ──
MAX_FOLLOW_UPS_PER_QUESTION = 1      # Avoid interrogation loops
INTERVIEW_TIMEOUT_SECONDS = 1800     # 30 minute max duration
