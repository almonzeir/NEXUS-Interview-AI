"""
🧠 NEXUS — AI Interview Agent v3.0 (Research Edition)
======================================================
An evidence-grounded adaptive interview system.

Architecture (Model-Agnostic):
  👂 Whisper Large V3 (STT)  — Speech recognition via Groq
  🧠 Qwen QwQ-32B (Brain)   — Question generation + scoring via Groq
  🗣️ Edge-TTS (Voice)        — Text-to-speech, runs locally

Research Pipeline:
  1. CV + JD Upload → Gap Analysis
  2. Personalized Question Generation (targets gaps)
  3. Voice Interview with Adaptive Follow-ups
  4. Per-Answer Scoring (0-5) with Evidence Quotes
  5. Structured Report (JSON + exportable)

Usage:
  1. Set GROQ_API_KEY in .env file
  2. Run: py nexus_server.py
  3. Open browser: http://localhost:8000
"""

import os
import sys
import re
import json
import time
import shutil
import asyncio
import tempfile
import traceback
from pathlib import Path
from datetime import datetime

# ── Load API key ──
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.strip().startswith("GROQ_API_KEY="):
                GROQ_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

if not GROQ_API_KEY:
    print("=" * 60)
    print("❌ GROQ_API_KEY not found!")
    print()
    print("Get your FREE key: https://console.groq.com")
    print("Then create a .env file with: GROQ_API_KEY=your_key_here")
    print("=" * 60)
    sys.exit(1)

# ── Imports ──
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from groq import Groq
import edge_tts
import uvicorn

print("🧠 NEXUS — AI Interview Agent v3.0 (Research Edition)")
print("=" * 55)

# ── Groq Client ──
client = Groq(api_key=GROQ_API_KEY)
print("✅ Groq API connected")

# ── Models ──
STT_MODEL = "whisper-large-v3"       # OpenAI Whisper — MIT License
LLM_MODEL = "llama-3.3-70b-versatile"  # Meta Llama 3.3 70B — Production, Apache 2.0
TTS_VOICE = "en-US-AndrewNeural"     # Professional male voice (Microsoft Andrew)

print(f"👂 STT: {STT_MODEL}")
print(f"🧠 LLM: {LLM_MODEL}")
print(f"🗣️ TTS: {TTS_VOICE}")

# ── Data directory for saving sessions ──
DATA_DIR = Path(__file__).parent / "sessions"
DATA_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════
# INTERVIEW SESSION STATE
# ══════════════════════════════════════════════════════════
# This holds the current interview session data.
# In a production system, you'd use a database.
# For research, a single-session server is fine.

session = {
    "id": None,               # Unique session ID
    "status": "idle",          # idle → setup → interviewing → completed
    "cv_text": "",             # Raw CV text
    "jd_text": "",             # Raw JD text
    "cv_analysis": {},         # Parsed CV data (skills, experience, etc.)
    "jd_analysis": {},         # Parsed JD data (requirements, etc.)
    "gap_analysis": {},        # Gaps between CV and JD
    "questions": [],           # Generated interview questions
    "current_question": 0,     # Index of current question
    "conversation": [],        # Full conversation history
    "scores": [],              # Per-answer scores with evidence
    "report": None,            # Final generated report
    "started_at": None,        # Timestamp
    "ended_at": None,          # Timestamp
    "timings": []              # Response latency data for research
}


def reset_session():
    """Reset the session to a clean state."""
    global session
    session = {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "status": "idle",
        "cv_text": "",
        "jd_text": "",
        "cv_analysis": {},
        "jd_analysis": {},
        "gap_analysis": {},
        "questions": [],
        "current_question": 0,
        "conversation": [],
        "scores": [],
        "report": None,
        "started_at": None,
        "ended_at": None,
        "timings": []
    }


reset_session()


# ══════════════════════════════════════════════════════════
# LLM HELPER — Clean Qwen responses
# ══════════════════════════════════════════════════════════

def clean_llm_response(text: str) -> str:
    """Remove <think>...</think> blocks that Qwen QwQ includes."""
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    return cleaned if cleaned else text.strip()


def call_llm(messages: list, max_tokens: int = 1000, temperature: float = 0.7) -> str:
    """Call the LLM via Groq and return cleaned response."""
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature
    )
    return clean_llm_response(response.choices[0].message.content)


def call_llm_json(messages: list, max_tokens: int = 2000) -> dict:
    """Call the LLM and parse JSON response. Falls back to text parsing."""
    raw = call_llm(messages, max_tokens=max_tokens, temperature=0.3)

    # Try to extract JSON from the response
    # LLMs sometimes wrap JSON in ```json ... ``` blocks
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw)
    if json_match:
        raw = json_match.group(1).strip()

    # Also try to find raw JSON object/array
    if not raw.startswith('{') and not raw.startswith('['):
        json_match = re.search(r'(\{[\s\S]*\})', raw)
        if json_match:
            raw = json_match.group(1)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"⚠️ Failed to parse LLM JSON. Raw response:\n{raw[:500]}")
        return {"error": "Failed to parse response", "raw": raw}


# ══════════════════════════════════════════════════════════
# STEP 1: CV + JD ANALYSIS
# ══════════════════════════════════════════════════════════

def analyze_cv(cv_text: str) -> dict:
    """
    Extract structured information from a CV/resume.
    We ask the LLM to pull out: skills, experience, education, projects.
    """
    messages = [
        {"role": "system", "content": """You are an expert CV/resume parser. 
Extract structured information from the following CV and return it as JSON.

Return EXACTLY this JSON format:
{
  "name": "candidate name",
  "skills": ["skill1", "skill2", ...],
  "experience_years": 0,
  "experiences": [
    {"title": "job title", "company": "company", "duration": "duration", "highlights": ["key achievement"]}
  ],
  "education": [
    {"degree": "degree", "institution": "institution", "year": "year"}
  ],
  "projects": ["project1", "project2"],
  "tools": ["tool1", "tool2"],
  "summary": "one-line summary of the candidate"
}

Return ONLY valid JSON, no other text."""},
        {"role": "user", "content": f"Parse this CV:\n\n{cv_text}"}
    ]
    return call_llm_json(messages)


def analyze_jd(jd_text: str) -> dict:
    """
    Extract structured requirements from a Job Description.
    """
    messages = [
        {"role": "system", "content": """You are an expert job description analyzer.
Extract structured requirements from the following Job Description and return as JSON.

Return EXACTLY this JSON format:
{
  "title": "job title",
  "company": "company name if mentioned",
  "required_skills": ["skill1", "skill2", ...],
  "preferred_skills": ["skill1", "skill2", ...],
  "experience_required": "e.g. 2-3 years",
  "education_required": "e.g. Bachelor's in CS",
  "key_responsibilities": ["responsibility1", "responsibility2", ...],
  "soft_skills": ["communication", "teamwork", ...],
  "summary": "one-line summary of the role"
}

Return ONLY valid JSON, no other text."""},
        {"role": "user", "content": f"Parse this Job Description:\n\n{jd_text}"}
    ]
    return call_llm_json(messages)


def analyze_gaps(cv_data: dict, jd_data: dict) -> dict:
    """
    Compare CV against JD to find gaps, matches, and areas to probe.
    THIS is the core of personalized interviewing.
    """
    messages = [
        {"role": "system", "content": """You are an expert HR analyst.
Compare the candidate's CV data against the Job Description requirements.
Identify matches, gaps, and areas that need deeper probing in an interview.

Return EXACTLY this JSON format:
{
  "match_score": 75,
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill3", "skill4"],
  "experience_gap": "description of experience gap or 'None'",
  "education_match": true,
  "strengths": ["strength1", "strength2"],
  "concerns": ["concern1", "concern2"],
  "probe_areas": [
    {"area": "area to probe", "reason": "why this needs deeper questioning", "priority": "high/medium/low"}
  ]
}

Return ONLY valid JSON, no other text."""},
        {"role": "user", "content": f"""CV Data:
{json.dumps(cv_data, indent=2)}

Job Description Data:
{json.dumps(jd_data, indent=2)}

Analyze the gaps."""}
    ]
    return call_llm_json(messages)


# ══════════════════════════════════════════════════════════
# STEP 2: QUESTION GENERATION
# ══════════════════════════════════════════════════════════

def generate_questions(cv_data: dict, jd_data: dict, gap_data: dict) -> list:
    """
    Generate personalized interview questions targeting identified gaps.
    Each question is linked to a specific gap/skill for evidence tracking.
    """
    messages = [
        {"role": "system", "content": """You are an expert interview designer.
Based on the CV analysis, Job Description, and identified gaps, generate 
6-8 targeted interview questions. Each question should probe a specific 
area of concern or verify a claimed skill.

IMPORTANT: Questions must be conversational (spoken out loud by an AI interviewer).
Do NOT use technical jargon in the question itself. Make them natural and clear.

Return EXACTLY this JSON format:
{
  "questions": [
    {
      "id": 1,
      "question": "the interview question text",
      "target_area": "what skill/gap this probes",
      "category": "technical/behavioral/situational/competency",
      "rubric_focus": "what a good answer would demonstrate",
      "follow_up_if_vague": "a follow-up question if the answer is vague"
    }
  ]
}

The first question should always be a warm greeting + ask them to introduce themselves.
The last question should give the candidate a chance to ask questions or add anything.

Return ONLY valid JSON, no other text."""},
        {"role": "user", "content": f"""CV Analysis:
{json.dumps(cv_data, indent=2)}

Job Description:
{json.dumps(jd_data, indent=2)}

Gap Analysis:
{json.dumps(gap_data, indent=2)}

Generate the interview questions."""}
    ]
    result = call_llm_json(messages, max_tokens=2000)
    return result.get("questions", [])


# ══════════════════════════════════════════════════════════
# STEP 3: PER-ANSWER SCORING (Evidence-Grounded)
# ══════════════════════════════════════════════════════════
# Upgrades for Research Accuracy:
#   1. Few-Shot Anchor Examples (model knows what each score level looks like)
#   2. Chain-of-Thought Reasoning (think step-by-step before scoring)
#   3. Low Temperature (0.2) for deterministic, reproducible scores

SCORING_RUBRIC = {
    "relevance": "Does the answer directly address the question asked?",
    "depth": "Does the candidate provide specific examples, metrics, or STAR method?",
    "competency": "Does the answer demonstrate the target skill or expertise?",
    "communication": "Is the answer clear, structured, and professionally delivered?"
}

# Few-shot anchor examples for calibration
SCORE_ANCHORS = """
SCORING GUIDE (use these anchors to calibrate):

SCORE 1 (Very Poor):
  Question: "Tell me about your experience with Python."
  Answer: "Yeah I know Python."
  Why 1: No specifics, no examples, single vague sentence.

SCORE 2 (Poor):
  Question: "Tell me about your experience with Python."
  Answer: "I've used Python for some projects in university. It was good."
  Why 2: Mentions usage context but zero specifics — no project names, no details.

SCORE 3 (Adequate):
  Question: "Tell me about your experience with Python."
  Answer: "I used Python in my final year project to build a web scraper that collected data from 3 websites."
  Why 3: Has a concrete example with some detail, but lacks depth on challenges/impact.

SCORE 4 (Good):
  Question: "Tell me about your experience with Python."
  Answer: "I built a REST API using FastAPI for my capstone project that handled product inventory for a local business. I used SQLAlchemy for the ORM and deployed it on Railway."
  Why 4: Specific project, named technologies, real-world application. Missing quantitative impact.

SCORE 5 (Excellent):
  Question: "Tell me about your experience with Python."
  Answer: "In my internship at TechCorp, I developed a data pipeline in Python using Pandas and Airflow that automated report generation for 200+ clients, reducing manual work by 15 hours per week. I also wrote unit tests with pytest achieving 92% coverage."
  Why 5: Real company, specific tools, quantitative impact (200+ clients, 15hrs saved, 92% coverage), demonstrates depth.
"""


def score_answer(question_data: dict, answer_text: str) -> dict:
    """
    Score a candidate's answer using Chain-of-Thought + Few-Shot calibration.
    Uses temperature=0.2 for reproducible, deterministic scoring.
    """
    messages = [
        {"role": "system", "content": f"""You are an expert interview evaluator for a research study.

RUBRIC DIMENSIONS (score each 0-5):
{json.dumps(SCORING_RUBRIC, indent=2)}

{SCORE_ANCHORS}

EVALUATION PROTOCOL (Chain-of-Thought):
Before assigning scores, you MUST think through these steps:
1. IDENTIFY what the question is specifically asking for.
2. EXTRACT the key claims and evidence from the candidate's answer.
3. COMPARE the answer against the scoring anchors above — which level does it most closely match?
4. ASSIGN scores with direct transcript quotes as evidence.
5. DETERMINE if a follow-up is needed (score < 3 on any dimension).

CRITICAL RULES:
- Every score MUST include a DIRECT QUOTE from the candidate's answer as evidence.
- If the candidate gave no relevant content, quote what they said and explain the gap.
- Do NOT penalise accent, grammar errors, or speaking style — score CONTENT only.
- Be calibrated: a score of 3 is AVERAGE, not bad. Reserve 5 for truly exceptional answers.
- Do NOT inflate scores. Most real interview answers fall between 2-4.

Return EXACTLY this JSON (no other text):
{{
  "chain_of_thought": "Your step-by-step reasoning before scoring",
  "scores": {{
    "relevance": {{
      "score": 0,
      "evidence": "direct quote from answer",
      "reasoning": "why this score, referencing anchor level"
    }},
    "depth": {{
      "score": 0,
      "evidence": "direct quote from answer",
      "reasoning": "why this score, referencing anchor level"
    }},
    "competency": {{
      "score": 0,
      "evidence": "direct quote from answer",
      "reasoning": "why this score, referencing anchor level"
    }},
    "communication": {{
      "score": 0,
      "evidence": "direct quote from answer",
      "reasoning": "why this score, referencing anchor level"
    }}
  }},
  "average_score": 0.0,
  "needs_follow_up": true,
  "follow_up_reason": "reason if any dimension scored below 3"
}}"""},
        {"role": "user", "content": f"""Question asked: {question_data.get('question', '')}
Target area being assessed: {question_data.get('target_area', '')}
What a good answer demonstrates: {question_data.get('rubric_focus', '')}

Candidate's answer: "{answer_text}"

Think step-by-step, then score this answer."""}
    ]
    # Temperature 0.2 for deterministic, reproducible scoring
    result = call_llm_json(messages, max_tokens=1500)

    # Calculate average if not provided
    if "scores" in result and "average_score" not in result:
        scores = result["scores"]
        total = sum(s.get("score", 0) for s in scores.values() if isinstance(s, dict))
        result["average_score"] = round(total / 4, 2)

    return result


# ══════════════════════════════════════════════════════════
# STEP 4: INTERVIEW BRAIN (Adaptive Follow-ups)
# ══════════════════════════════════════════════════════════

def get_next_response(transcript: str) -> tuple:
    """
    Decides what NEXUS says next:
    - If the answer needs follow-up → ask follow-up
    - Otherwise → ask next question
    - If all questions done → wrap up

    Returns: (response_text, is_interview_complete)
    """
    global session

    q_index = session["current_question"]
    questions = session["questions"]

    # Score the answer (skip for the first greeting exchange)
    if q_index > 0 and transcript and transcript != "...":
        current_q = questions[min(q_index - 1, len(questions) - 1)]
        print(f"📊 Scoring answer for Q{q_index}...")
        score_data = score_answer(current_q, transcript)
        score_data["question_id"] = current_q.get("id", q_index)
        score_data["question_text"] = current_q.get("question", "")
        score_data["answer_text"] = transcript
        session["scores"].append(score_data)
        avg = score_data.get("average_score", 0)
        print(f"📊 Score: {avg}/5.0")

    # Check if we need a follow-up (MAX 1 per question, then move on)
    followed_up_key = f"followed_up_q{q_index - 1}"
    already_followed_up = session.get(followed_up_key, False)

    if (not already_followed_up
        and session["scores"]
        and session["scores"][-1].get("needs_follow_up", False)
        and session["scores"][-1].get("average_score", 5) < 3):

        follow_up = questions[min(q_index - 1, len(questions) - 1)].get("follow_up_if_vague", "")
        if follow_up:
            session[followed_up_key] = True  # Mark: we already followed up on this question
            messages = [
                {"role": "system", "content": "You are NEXUS, a professional AI interviewer. Naturally ask a follow-up question to get more detail. Keep it to 1-2 sentences. Speak naturally, no markdown."},
                {"role": "user", "content": f"The candidate gave a vague answer. Ask this follow-up naturally: {follow_up}"}
            ]
            response = call_llm(messages, max_tokens=100)
            session["conversation"].append({"role": "user", "content": transcript, "timestamp": time.time()})
            session["conversation"].append({"role": "assistant", "content": response, "timestamp": time.time()})
            return response, False

    # Move to next question
    if q_index < len(questions):
        question = questions[q_index]
        session["current_question"] = q_index + 1

        # Make the question sound natural (not robotic)
        if q_index == 0:
            # First question: greeting
            response = question["question"]
        else:
            # Transition naturally between questions
            messages = [
                {"role": "system", "content": """You are NEXUS, a professional AI interviewer conducting a voice interview.
Transition naturally to the next question. You can briefly acknowledge the previous answer 
(1 short sentence) then ask the question. Keep it conversational and warm.
Do NOT use markdown, bullet points, or formatting. Speak naturally.
Keep total response under 3 sentences."""},
                {"role": "user", "content": f"""The candidate just said: "{transcript}"
                
Now transition to this next question: "{question['question']}"

Say it naturally as a human interviewer would."""}
            ]
            response = call_llm(messages, max_tokens=150)

        session["conversation"].append({"role": "user", "content": transcript, "timestamp": time.time()})
        session["conversation"].append({"role": "assistant", "content": response, "timestamp": time.time()})
        return response, False
    else:
        # All questions asked — wrap up
        session["status"] = "completed"
        session["ended_at"] = datetime.now().isoformat()
        response = "Thank you so much for taking the time to speak with me today. You've given some really thoughtful answers, and I appreciate your openness. We'll review everything and get back to you soon. Have a great day!"
        session["conversation"].append({"role": "user", "content": transcript, "timestamp": time.time()})
        session["conversation"].append({"role": "assistant", "content": response, "timestamp": time.time()})
        return response, True


# ══════════════════════════════════════════════════════════
# STEP 5: REPORT GENERATION
# ══════════════════════════════════════════════════════════

def generate_report() -> dict:
    """
    Generate the final interview report with all scores,
    evidence, and an overall recommendation.
    """
    global session

    # Calculate overall metrics
    all_scores = [s for s in session["scores"] if "scores" in s]
    if all_scores:
        avg_relevance = sum(s["scores"]["relevance"]["score"] for s in all_scores if isinstance(s["scores"].get("relevance"), dict)) / len(all_scores)
        avg_depth = sum(s["scores"]["depth"]["score"] for s in all_scores if isinstance(s["scores"].get("depth"), dict)) / len(all_scores)
        avg_competency = sum(s["scores"]["competency"]["score"] for s in all_scores if isinstance(s["scores"].get("competency"), dict)) / len(all_scores)
        avg_communication = sum(s["scores"]["communication"]["score"] for s in all_scores if isinstance(s["scores"].get("communication"), dict)) / len(all_scores)
        overall_avg = (avg_relevance + avg_depth + avg_competency + avg_communication) / 4
    else:
        avg_relevance = avg_depth = avg_competency = avg_communication = overall_avg = 0

    # Generate AI recommendation
    messages = [
        {"role": "system", "content": """You are an expert HR analyst writing a final interview assessment.
Based on the interview data, write a brief professional recommendation.

Return EXACTLY this JSON format:
{
  "recommendation": "RECOMMEND / CONSIDER / DO NOT RECOMMEND",
  "summary": "2-3 sentence overall assessment",
  "strengths": ["strength 1", "strength 2"],
  "areas_for_development": ["area 1", "area 2"],
  "hiring_confidence": 75
}

Return ONLY valid JSON, no other text."""},
        {"role": "user", "content": f"""Interview Scores:
- Relevance: {avg_relevance:.1f}/5
- Depth: {avg_depth:.1f}/5
- Competency: {avg_competency:.1f}/5
- Communication: {avg_communication:.1f}/5
- Overall: {overall_avg:.1f}/5

Candidate CV: {json.dumps(session['cv_analysis'], indent=2)}
Job: {json.dumps(session['jd_analysis'], indent=2)}
Gaps Found: {json.dumps(session['gap_analysis'], indent=2)}

Per-question scores:
{json.dumps([{
    'question': s.get('question_text', ''),
    'average': s.get('average_score', 0),
    'answer_excerpt': s.get('answer_text', '')[:100]
} for s in all_scores], indent=2)}

Generate the recommendation."""}
    ]
    recommendation = call_llm_json(messages, max_tokens=500)

    report = {
        "session_id": session["id"],
        "generated_at": datetime.now().isoformat(),
        "candidate": session["cv_analysis"],
        "job": session["jd_analysis"],
        "gap_analysis": session["gap_analysis"],
        "interview_duration": None,
        "total_questions": len(session["questions"]),
        "questions_answered": len(all_scores),
        "rubric_scores": {
            "relevance": round(avg_relevance, 2),
            "depth": round(avg_depth, 2),
            "competency": round(avg_competency, 2),
            "communication": round(avg_communication, 2),
            "overall": round(overall_avg, 2)
        },
        "per_question_scores": session["scores"],
        "recommendation": recommendation,
        "transcript": session["conversation"],
        "response_latencies": session["timings"],
        "model_info": {
            "stt": STT_MODEL,
            "llm": LLM_MODEL,
            "tts": TTS_VOICE,
            "provider": "Groq"
        }
    }

    # Calculate duration
    if session["started_at"] and session["ended_at"]:
        try:
            start = datetime.fromisoformat(session["started_at"])
            end = datetime.fromisoformat(session["ended_at"])
            report["interview_duration"] = str(end - start)
        except Exception:
            pass

    session["report"] = report
    return report


def save_session():
    """Save the full session data to a JSON file for research analysis."""
    filepath = DATA_DIR / f"session_{session['id']}.json"
    data = {
        "session": session,
        "report": session.get("report"),
        "metadata": {
            "saved_at": datetime.now().isoformat(),
            "models": {"stt": STT_MODEL, "llm": LLM_MODEL, "tts": TTS_VOICE}
        }
    }
    filepath.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"💾 Session saved: {filepath}")
    return filepath


# ══════════════════════════════════════════════════════════
# SPEECH ENGINES
# ══════════════════════════════════════════════════════════

def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio using Groq Whisper."""
    with open(audio_path, "rb") as f:
        transcription = client.audio.transcriptions.create(
            model=STT_MODEL,
            file=f,
            language="en"
        )
    return transcription.text.strip()


async def _generate_speech(text: str, path: str) -> str:
    """Generate speech audio from text using Edge-TTS."""
    communicate = edge_tts.Communicate(text, TTS_VOICE, rate="+10%")
    await communicate.save(path)
    return path


def speak(text: str) -> str:
    """Synchronous TTS wrapper — ONLY for startup test."""
    output_path = os.path.join(tempfile.gettempdir(), "nexus_response.mp3")
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_generate_speech(text, output_path))
    finally:
        loop.close()
    return output_path


async def speak_async(text: str) -> str:
    """Async TTS — used during interview (inside FastAPI's event loop)."""
    output_path = os.path.join(tempfile.gettempdir(), "nexus_response.mp3")
    await _generate_speech(text, output_path)
    return output_path


# ══════════════════════════════════════════════════════════
# FASTAPI SERVER
# ══════════════════════════════════════════════════════════

app = FastAPI(title="NEXUS AI Interview Agent", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Transcript", "X-Response", "X-Score", "X-Complete"]
)


# ── Serve UI ──
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    ui_path = Path(__file__).parent / "nexus_ui.html"
    if ui_path.exists():
        return HTMLResponse(content=ui_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>NEXUS is running! Place nexus_ui.html in same folder.</h1>")


@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "agent": "NEXUS",
        "version": "3.0-research",
        "session_status": session["status"],
        "models": {"stt": STT_MODEL, "llm": LLM_MODEL, "tts": TTS_VOICE}
    }


# ── SETUP: Upload CV + JD ──
@app.post("/setup")
async def setup_interview(
    cv_text: str = Form(...),
    jd_text: str = Form(...)
):
    """
    Step 1 of the interview pipeline:
    - Receive CV and JD text
    - Analyze both
    - Find gaps
    - Generate personalized questions
    """
    global session
    reset_session()

    try:
        print("📄 Analyzing CV...")
        t1 = time.time()
        session["cv_text"] = cv_text
        session["cv_analysis"] = analyze_cv(cv_text)
        t2 = time.time()
        if "error" in session["cv_analysis"]:
            print(f"  ⚠️ CV parse issue, using raw data")
            session["cv_analysis"] = {"skills": [], "experience": [], "raw": cv_text[:500]}
        print(f"  ✅ CV analyzed ({t2-t1:.1f}s)")

        print("📋 Analyzing Job Description...")
        session["jd_text"] = jd_text
        session["jd_analysis"] = analyze_jd(jd_text)
        t3 = time.time()
        if "error" in session["jd_analysis"]:
            print(f"  ⚠️ JD parse issue, using raw data")
            session["jd_analysis"] = {"required_skills": [], "responsibilities": [], "raw": jd_text[:500]}
        print(f"  ✅ JD analyzed ({t3-t2:.1f}s)")

        print("🔍 Analyzing gaps...")
        session["gap_analysis"] = analyze_gaps(session["cv_analysis"], session["jd_analysis"])
        t4 = time.time()
        print(f"  ✅ Gaps identified ({t4-t3:.1f}s)")

        print("❓ Generating personalized questions...")
        session["questions"] = generate_questions(
            session["cv_analysis"],
            session["jd_analysis"],
            session["gap_analysis"]
        )
        t5 = time.time()
        print(f"  ✅ {len(session['questions'])} questions generated ({t5-t4:.1f}s)")

        session["status"] = "ready"
        session["started_at"] = datetime.now().isoformat()

        print(f"⏱️  Total setup: {t5-t1:.1f}s")
        print("─" * 50)

        return {
            "status": "ready",
            "cv_analysis": session["cv_analysis"],
            "jd_analysis": session["jd_analysis"],
            "gap_analysis": session["gap_analysis"],
            "question_count": len(session["questions"]),
            "questions_preview": [q["question"] for q in session["questions"]]
        }

    except Exception as e:
        print(f"❌ Setup error: {e}")
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


# ── INTERVIEW: Start (Welcome + First Question) ──
@app.post("/start")
async def start_interview_endpoint():
    """
    Called once when the interview begins.
    Generates a welcome greeting + first question as audio.
    """
    global session

    if session["status"] not in ("ready", "interviewing"):
        return JSONResponse(
            {"error": "Interview not set up. Call /setup first."},
            status_code=400
        )

    session["status"] = "interviewing"

    try:
        # Get candidate name from CV analysis
        candidate_name = session.get("cv_analysis", {}).get("name", "")
        first_question = session["questions"][0]["question"] if session["questions"] else "Tell me about yourself."

        # Generate a natural welcome + first question
        messages = [
            {"role": "system", "content": """You are NEXUS, a professional AI interviewer conducting a voice-based competency assessment.
Generate a warm but professional welcome greeting that:
1. Welcomes the candidate by name (if available)
2. Briefly introduces yourself as an AI interviewer
3. Explains the format (voice-based, several questions, just be natural)
4. Naturally transitions into the first question

Keep it to 4-5 sentences total. Speak naturally. No markdown, no bullet points.
End by asking the first question."""},
            {"role": "user", "content": f"""Candidate name: {candidate_name or 'the candidate'}
First question to ask: \"{first_question}\"

Generate the welcome greeting that ends with this first question."""}
        ]

        welcome = call_llm(messages, max_tokens=250, temperature=0.7)
        print(f"\U0001f399\ufe0f Welcome: {welcome}")

        # Record in session
        session["current_question"] = 1  # Mark first question as asked
        session["conversation"].append({
            "role": "assistant",
            "content": welcome,
            "timestamp": time.time(),
            "type": "welcome"
        })

        # Generate audio
        audio_path = await speak_async(welcome)

        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            headers={
                "X-Response": welcome.replace('\n', ' ')[:500],
                "X-Welcome": "true"
            }
        )

    except Exception as e:
        print(f"\u274c Start error: {e}")
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


# ── INTERVIEW: Voice Chat ──
@app.post("/chat")
async def chat_endpoint(file: UploadFile = File(...)):
    """
    Main interview loop:
    Audio in → Transcribe → Score previous → Get next question → Speak → Audio out
    """
    global session

    if session["status"] not in ("ready", "interviewing"):
        return JSONResponse(
            {"error": "Interview not set up. Call /setup first."},
            status_code=400
        )

    session["status"] = "interviewing"

    try:
        start = time.time()

        # 1. Save uploaded audio
        temp_input = os.path.join(tempfile.gettempdir(), "nexus_input.webm")
        with open(temp_input, "wb") as f:
            shutil.copyfileobj(file.file, f)
        t1 = time.time()

        # 2. Transcribe
        transcript = transcribe_audio(temp_input) or "..."
        t2 = time.time()
        print(f"👂 [{t2-t1:.1f}s] Candidate: {transcript}")

        # 3. Get next response (includes scoring + question generation)
        response, is_complete = get_next_response(transcript)
        t3 = time.time()
        print(f"🧠 [{t3-t2:.1f}s] NEXUS: {response}")

        # 4. Speak
        audio_path = await speak_async(response)
        t4 = time.time()
        print(f"🗣️ [{t4-t3:.1f}s] Audio generated")
        print(f"⏱️  Total: {t4-start:.1f}s")

        # Record timing for research
        session["timings"].append({
            "turn": len(session["timings"]) + 1,
            "stt_time": round(t2 - t1, 3),
            "llm_time": round(t3 - t2, 3),
            "tts_time": round(t4 - t3, 3),
            "total_time": round(t4 - start, 3)
        })

        # Get latest score for UI
        latest_score = ""
        if session["scores"]:
            latest_score = str(session["scores"][-1].get("average_score", ""))

        # If interview is complete, generate report and save
        if is_complete:
            print("📊 Generating final report...")
            generate_report()
            save_session()
            print("✅ Interview complete! Report generated.")

        print("─" * 50)

        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            headers={
                "X-Transcript": transcript.replace('\n', ' ')[:500],
                "X-Response": response.replace('\n', ' ')[:500],
                "X-Score": latest_score,
                "X-Complete": "true" if is_complete else "false"
            }
        )

    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


# ── GET REPORT ──
@app.get("/report")
async def get_report():
    """Return the interview report."""
    if session["report"]:
        return session["report"]

    # Generate if not yet done
    if session["scores"]:
        session["ended_at"] = session["ended_at"] or datetime.now().isoformat()
        report = generate_report()
        save_session()
        return report

    return JSONResponse(
        {"error": "No interview data yet. Complete an interview first."},
        status_code=404
    )


# ── GET SESSION STATUS ──
@app.get("/session")
async def get_session_status():
    """Return current session state (for UI updates)."""
    return {
        "status": session["status"],
        "current_question": session["current_question"],
        "total_questions": len(session["questions"]),
        "scores_so_far": len(session["scores"]),
        "latest_score": session["scores"][-1] if session["scores"] else None
    }


# ── RESET ──
@app.post("/reset")
async def reset():
    """Reset the interview session."""
    reset_session()
    return {"status": "reset", "message": "Session cleared. Ready for new interview."}


# ── LIST SAVED SESSIONS (for research) ──
@app.get("/sessions")
async def list_sessions():
    """List all saved interview sessions."""
    sessions = []
    for f in sorted(DATA_DIR.glob("session_*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sessions.append({
                "filename": f.name,
                "session_id": data.get("session", {}).get("id", ""),
                "status": data.get("session", {}).get("status", ""),
                "started_at": data.get("session", {}).get("started_at", ""),
            })
        except Exception:
            pass
    return {"sessions": sessions}


# ══════════════════════════════════════════════════════════
# LAUNCH
# ══════════════════════════════════════════════════════════

# Test TTS on startup
try:
    speak("System ready.")
    print("✅ Voice engine working")
except Exception as e:
    print(f"⚠️ Voice test: {e}")

if __name__ == "__main__":
    print()
    print("=" * 55)
    print("🚀 NEXUS v3.0 starting on http://localhost:8000")
    print("=" * 55)
    print()
    print("📋 How to use:")
    print("  1. Open http://localhost:8000 in your browser")
    print("  2. Upload a CV and Job Description")
    print("  3. Click the orb to start the interview")
    print("  4. View the report when complete")
    print()
    uvicorn.run(app, host="0.0.0.0", port=8000)
