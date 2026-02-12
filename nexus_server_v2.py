"""
NEXUS v3.0 (Async/High-Performance)
===================================
Research-grade AI Interview Agent running on FastAPI + Asyncio.

Features:
- Non-blocking I/O
- Parallel CV/JD Analysis
- Structured Data Validation (Pydantic)
- Robust Error Handling
- Camera & Eye Contact Support
"""

import os
import shutil
import logging
import asyncio
import tempfile
import uvicorn
import json
import aiofiles
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import edge_tts

# Import Core Logic
from nexus_core.orchestrator import orchestrator, SessionManager
from nexus_core.llm_gateway import llm_gateway
from nexus_core.structs import InterviewSession, EyeContactMetric

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NEXUS Research Engine", version="3.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Transcript", "X-Response", "X-Score", "X-Complete", "X-Session-ID"]
)

# ── HELPER: Audio Services ──

async def transcribe_audio(file_path: str) -> str:
    """Async wrapper for Whisper STT via Groq."""
    try:
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()

        # Groq's async client for audio
        client = llm_gateway._get_client() # Get a client (key rotation)

        # We pass (filename, content) tuple to mimic file object for httpx
        transcription = await client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=("audio.webm", content),
            language="en"
        )
        return transcription.text.strip()
    except Exception as e:
        logger.error(f"STT Error: {e}")
        return "..." # Fallback for silence/error

async def generate_speech(text: str) -> str:
    """Generate TTS audio file asynchronously."""
    fd, output_path = tempfile.mkstemp(suffix=".mp3", prefix="nexus_resp_")
    os.close(fd)

    voice = "en-US-AndrewNeural" # Professional male
    communicate = edge_tts.Communicate(text, voice, rate="+10%")
    await communicate.save(output_path)
    return output_path

# ── ENDPOINTS ──

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the research UI."""
    # Check for v2 UI first
    ui_path = Path("nexus_ui_v2.html")
    if not ui_path.exists():
        ui_path = Path("nexus_ui.html") # Fallback

    if ui_path.exists():
        return HTMLResponse(content=ui_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>NEXUS Core is Active. UI file not found.</h1>")

@app.post("/setup")
async def setup_session(
    cv_text: str = Form(...),
    jd_text: str = Form(...)
):
    """
    Initialize a new interview session.
    Triggers parallel analysis of CV and JD.
    """
    try:
        # Create Session
        session = SessionManager.create_session()
        logger.info(f"Created Session: {session.id}")

        # Run Analysis (This is the heavy lifting)
        # We await it here so the client knows when it's ready.
        # For huge docs, could be background task + polling.
        analysis_result = await orchestrator.analyze_candidate(session.id, cv_text, jd_text)

        return {
            "session_id": session.id,
            "status": "ready",
            "candidate": analysis_result["cv"],
            "job": analysis_result["jd"],
            "gaps": analysis_result["gaps"],
            "questions_preview": [q.question for q in analysis_result["questions"]]
        }
    except Exception as e:
        logger.error(f"Setup Failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/start")
async def start_interview(session_id: str = Form(...)):
    """
    Begin the interview. Returns the welcome message audio.
    """
    session = SessionManager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    try:
        # Generate Welcome
        name = session.cv_analysis.name if session.cv_analysis else "there"
        first_q = await orchestrator.get_next_question(session_id)

        welcome_prompt = f"Welcome the candidate named '{name}' to the interview. Briefly introduce yourself as NEXUS. Then ask the first question: '{first_q}'."
        welcome_text = await llm_gateway.generate_text("You are a professional interviewer.", welcome_prompt)

        # Generate Audio
        audio_path = await generate_speech(welcome_text)

        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            headers={
                "X-Response": welcome_text[:4000] if welcome_text else "", # safe header length
                "X-Session-ID": session_id,
                "Access-Control-Expose-Headers": "X-Response, X-Session-ID"
            }
        )
    except Exception as e:
        logger.error(f"Start Failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/chat")
async def chat_loop(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    eye_metrics: str = Form(None) # JSON string of EyeContactMetric list
):
    """
    Main Interview Loop: Audio In -> STT -> Logic -> TTS -> Audio Out
    Also accepts eye_metrics JSON string.
    """
    session = SessionManager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    # Use a unique temp file for this request
    fd, temp_input = tempfile.mkstemp(suffix=".webm", prefix=f"input_{session_id}_")
    os.close(fd)

    try:
        # Parse Eye Metrics
        metrics = []
        if eye_metrics:
            try:
                raw_list = json.loads(eye_metrics)
                for item in raw_list:
                    metrics.append(EyeContactMetric(**item))
            except Exception as e:
                logger.warning(f"Failed to parse eye metrics: {e}")

        # 1. Save Audio (Non-blocking read/write)
        async with aiofiles.open(temp_input, "wb") as f:
            while content := await file.read(1024 * 1024): # 1MB chunks
                await f.write(content)

        # 2. Transcribe (STT)
        transcript = await transcribe_audio(temp_input)
        logger.info(f"[{session_id}] Candidate: {transcript}")

        session.conversation_history.append({"role": "user", "content": transcript})

        # 3. Process Answer (Logic Core)
        response_text, is_complete = await orchestrator.process_answer(session_id, transcript, metrics)
        logger.info(f"[{session_id}] NEXUS: {response_text}")

        session.conversation_history.append({"role": "assistant", "content": response_text})

        # 4. Generate Speech (TTS)
        audio_path = await generate_speech(response_text)

        # Headers for UI update
        latest_score = "0"
        if session.scores:
            latest_score = str(session.scores[-1].average_score)

        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            headers={
                "X-Transcript": transcript[:500] if transcript else "",
                "X-Response": response_text[:4000] if response_text else "", # Truncate for headers
                "X-Score": latest_score,
                "X-Complete": "true" if is_complete else "false",
                "Access-Control-Expose-Headers": "X-Transcript, X-Response, X-Score, X-Complete"
            }
        )

    except Exception as e:
        logger.error(f"Chat Loop Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        # Cleanup input file
        if os.path.exists(temp_input):
            os.remove(temp_input)

@app.get("/report")
async def get_report(session_id: str):
    """Generate and return the final JSON report."""
    try:
        report = await orchestrator.generate_final_report(session_id)
        return report
    except ValueError:
        raise HTTPException(404, "Session not found")
    except Exception as e:
        logger.error(f"Report Generation Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/debug/sessions")
async def debug_sessions():
    """List active sessions (Debug only)."""
    return [s.id for s in SessionManager.list_sessions()]

if __name__ == "__main__":
    uvicorn.run("nexus_server_v2:app", host="0.0.0.0", port=8000, reload=True)
