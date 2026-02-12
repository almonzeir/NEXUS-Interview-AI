# IV. System Architecture

## A. Overview

NEXUS is architected as a single-server web application built on the FastAPI framework (Python 3.11), designed for real-time voice-based competency assessment. The system follows a five-stage sequential pipeline, with each stage producing structured JSON artifacts that feed into the next. Fig. 1 presents the high-level system architecture.

```
┌──────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser)                       │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  Setup View  │  │ Interview UI │  │  Assessment Report   │ │
│  │  (CV + JD)   │  │  (3D Mic +   │  │  (Print-Ready PDF)   │ │
│  │              │  │   Sidebar)   │  │                      │ │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────┘ │
│         │                 │                                    │
│         │  REST API       │  REST API + Audio Blobs            │
└─────────┼─────────────────┼────────────────────────────────────┘
          │                 │
          ▼                 ▼
┌──────────────────────────────────────────────────────────────┐
│                     NEXUS SERVER (FastAPI)                     │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  STAGE 1: Input Processing                             │   │
│  │  ┌──────────────┐  ┌──────────────┐                    │   │
│  │  │  analyze_cv() │  │  analyze_jd() │                    │   │
│  │  │  (LLM Parse)  │  │  (LLM Parse)  │                    │   │
│  │  └──────┬────────┘  └──────┬────────┘                    │   │
│  │         └───────┬──────────┘                             │   │
│  │                 ▼                                        │   │
│  │  ┌──────────────────────┐                                │   │
│  │  │  analyze_gaps()       │  ← Comparative Analysis       │   │
│  │  │  matched | missing |  │                                │   │
│  │  │  probe_areas          │                                │   │
│  │  └──────────┬────────────┘                                │   │
│  └─────────────┼─────────────────────────────────────────────┘   │
│                ▼                                               │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  STAGE 2: Question Generation                          │   │
│  │  generate_questions(cv, jd, gaps)                       │   │
│  │  → 8 targeted questions with rubric_focus               │   │
│  └──────────────────────┬─────────────────────────────────┘   │
│                         ▼                                      │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  STAGE 3: Voice Interview Loop                         │   │
│  │  ┌────────────┐  ┌─────────────┐  ┌───────────────┐   │   │
│  │  │ Whisper V3  │→ │ score_answer│→ │get_next_      │   │   │
│  │  │ (STT)       │  │ (CoT+Few-  │  │response()     │   │   │
│  │  │             │  │  Shot)      │  │(Adaptive)     │   │   │
│  │  └─────────────┘  └─────────────┘  └──────┬────────┘   │   │
│  │                                           │             │   │
│  │                  ┌────────────────────────┘             │   │
│  │                  ▼                                      │   │
│  │  ┌─────────────────────┐                                │   │
│  │  │  Edge-TTS (Andrew)   │  → Audio Response to Client   │   │
│  │  └─────────────────────┘                                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                         ▼                                      │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  STAGE 4: Report Generation                            │   │
│  │  generate_report() → JSON + Structured Assessment       │   │
│  └────────────────────────────────────────────────────────┘   │
│                         ▼                                      │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  STAGE 5: Session Persistence                          │   │
│  │  save_session() → sessions/session_{id}.json            │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                               │
│  External APIs:  Groq (LLM + STT)  |  Edge-TTS (local)       │
└──────────────────────────────────────────────────────────────┘
```

**Fig. 1.** High-level architecture of the NEXUS Automated Competency Assessment System showing the five-stage sequential pipeline.

---

## B. Technology Stack

Table I summarizes the technologies and models used in the system.

| Component | Technology | Role |
|---|---|---|
| Web Framework | FastAPI (Python 3.11) | REST API server, async request handling |
| LLM Inference | Groq Cloud API | Hosts LLM on custom LPU hardware |
| Language Model | Meta Llama 3.3 70B Versatile | CV/JD analysis, question generation, scoring |
| Speech-to-Text | OpenAI Whisper Large V3 (via Groq) | Real-time audio transcription |
| Text-to-Speech | Microsoft Edge-TTS (en-US-AndrewNeural) | AI interviewer voice synthesis |
| Frontend | HTML5, CSS3, JavaScript (Vanilla) | Single-page research dashboard |
| Deployment | Railway (Docker) | Cloud hosting with auto-deployment |
| Data Persistence | JSON files | Session logs for research analysis |

**Table I.** Technology stack of the NEXUS system.

The decision to use Groq's free-tier inference was deliberate: it demonstrates that research-grade AI interview systems can operate at **zero marginal cost**, supporting the democratization of AI-assisted recruitment in resource-constrained environments.

---

## C. Stage 1: Input Processing and Gap Analysis

The interview pipeline begins when the evaluator submits two text inputs: the candidate's CV/resume and the target Job Description (JD). Both documents undergo LLM-powered structured extraction.

### C.1 CV Analysis (`analyze_cv`)

The candidate's CV is parsed by the LLM into a structured JSON object containing:

- **Skills**: Technical and soft skills mentioned
- **Experience**: Roles, durations, and responsibilities
- **Education**: Degrees, institutions, and fields of study
- **Projects**: Notable projects with technologies used

### C.2 JD Analysis (`analyze_jd`)

The Job Description is similarly parsed to extract:

- **Required Skills**: Mandatory technical competencies
- **Preferred Skills**: Nice-to-have qualifications
- **Responsibilities**: Core duties of the role
- **Success Criteria**: What defines successful performance

### C.3 Comparative Gap Analysis (`analyze_gaps`)

The core innovation of NEXUS lies in its **comparative gap analysis**. The system compares the structured CV against the structured JD to produce three categories:

1. **Matched Skills** — Competencies present in both CV and JD (displayed as green indicators)
2. **Missing Skills** — JD requirements absent from the CV (displayed as red indicators)
3. **Probe Areas** — Skills claimed in the CV that require deeper verification (displayed as amber indicators)

A numerical **Match Score** (0–100%) is computed to quantify the CV-JD alignment. This gap analysis directly drives the question generation stage, ensuring every interview question targets a specific identified gap or verification area.

---

## D. Stage 2: Personalized Question Generation

The `generate_questions` function receives the CV analysis, JD analysis, and gap analysis as inputs. It constructs a detailed LLM prompt requesting **8 interview questions**, each containing:

```json
{
    "question": "Can you walk me through a specific project where you implemented...",
    "target_area": "RAG pipeline implementation",
    "rubric_focus": "Candidate should demonstrate hands-on experience with...",
    "gap_type": "missing"
}
```

Each question is explicitly linked to a gap type (`matched`, `missing`, or `probe`), creating a traceable chain from gap identification → question → scoring. This **evidence chain** is a key contribution for research reproducibility.

---

## E. Stage 3: Voice Interview Loop

The interview operates as an asynchronous request-response cycle between the client browser and the FastAPI server.

### E.1 Speech-to-Text Pipeline

1. The candidate presses and holds the Spacebar to record audio in the browser
2. Audio is captured as a WebM blob via the MediaRecorder API
3. The blob is uploaded to the `/chat` endpoint as a multipart form
4. The server saves the audio to a temporary file
5. Groq's Whisper Large V3 transcribes the audio to text
6. The transcript is stored in the session for scoring

### E.2 Scoring Engine (`score_answer`)

Each candidate response is evaluated in real-time using a research-grade scoring protocol with three prompt engineering techniques:

1. **Few-Shot Anchor Calibration**: Five reference answer-score pairs spanning the full 0–5 range are provided as exemplars, giving the LLM concrete examples of what each score level looks like.

2. **Chain-of-Thought Evaluation**: The LLM is required to articulate step-by-step reasoning before assigning numerical scores, following the protocol:
   - IDENTIFY what the question asks
   - EXTRACT key claims from the answer
   - COMPARE against scoring anchors
   - ASSIGN scores with direct quotes

3. **Temperature Control** (τ = 0.2): Scoring inference uses a low temperature setting to minimize stochastic variation across evaluations, enhancing reproducibility.

The four scoring dimensions are:

| Dimension | Description |
|---|---|
| **Relevance** (0–5) | Does the answer directly address the question? |
| **Depth** (0–5) | Does the candidate provide specific examples, metrics, or STAR method? |
| **Competency** (0–5) | Does the answer demonstrate the target skill? |
| **Communication** (0–5) | Is the answer clear, structured, and professional? |

**Table II.** NEXUS scoring rubric dimensions.

Every score **must** include a direct transcript quote as evidence. Scores without evidence are flagged as invalid. This evidence-grounded approach enables post-hoc verification by human evaluators.

### E.3 Adaptive Follow-Up Logic (`get_next_response`)

The system implements a conditional follow-up mechanism:

- If **any dimension scores below 3**, the system generates a targeted follow-up question probing the weak area
- A maximum of **one follow-up** is permitted per primary question to prevent repetitive probing
- Follow-up tracking is maintained via a `followed_up_key` set in the session state

This adaptive behavior is inspired by structured interview best practices, where interviewers probe insufficiently answered questions while maintaining interview flow.

### E.4 Text-to-Speech Output

The AI interviewer's response is converted to speech using Microsoft Edge-TTS with the `en-US-AndrewNeural` voice at +10% speed rate. The generated MP3 audio file is served to the client via a static file endpoint (`/audio/{filename}`).

---

## F. Stage 4: Report Generation

Upon interview completion, the `generate_report` function aggregates all session data into a structured assessment report containing:

- **Executive Summary**: LLM-generated narrative assessment
- **Per-Question Breakdown**: Each question with its score, evidence quotes, and follow-up status
- **Dimensional Averages**: Mean scores across Relevance, Depth, Competency, and Communication
- **Overall Score**: Weighted average across all questions
- **Strengths and Weaknesses**: Identified from scoring patterns

The report is designed to be **print-ready** and follows academic assessment formatting conventions.

---

## G. Stage 5: Data Persistence

Each interview session is automatically saved as a JSON file in the `sessions/` directory with the naming convention `session_{uuid}.json`. The persisted data includes:

- Full session state (CV, JD, analysis, questions, scores)
- All candidate transcripts with timestamps
- Model metadata (STT model, LLM model, TTS voice)
- Response latency timings for performance analysis

This persistence layer enables:
1. Post-hoc comparison of AI scores against human evaluator scores
2. Inter-rater reliability analysis (Cohen's κ)
3. Reproducibility of the evaluation process

---

## H. Client-Side Architecture

The frontend is implemented as a single HTML file (`nexus_ui.html`) containing embedded CSS and JavaScript, served directly by the FastAPI server at the root path (`/`).

The UI operates across three screens:

1. **Setup Screen**: Two-panel layout for CV and JD input, with a gap analysis visualization showing matched, missing, and probe skills as color-coded chips alongside a circular match score indicator.

2. **Interview Screen**: Features a 3D CSS microphone visualization that provides visual feedback during recording (indigo glow) and AI speech (green glow). A scoring sidebar displays real-time evaluation results with evidence quotes as the interview progresses.

3. **Report Overlay**: A print-formatted assessment document rendered on a white background, suitable for export and inclusion in evaluation records.

---

## I. Deployment Architecture

The system is deployed on Railway, a cloud platform that supports persistent Python server processes. The deployment configuration consists of:

- `Procfile`: Defines the web process as `uvicorn nexus_server:app --host 0.0.0.0 --port $PORT`
- `runtime.txt`: Specifies Python 3.11
- `requirements.txt`: Lists five dependencies (FastAPI, Uvicorn, Groq SDK, Edge-TTS, python-dotenv)

The `GROQ_API_KEY` environment variable is configured through Railway's dashboard, ensuring API credentials are never committed to version control. The system auto-detects its deployment URL via `window.location.origin`, enabling seamless operation on both localhost and cloud environments.

---

## J. Design Decisions and Trade-offs

Several architectural decisions merit discussion:

1. **Single-file frontend**: While a framework like React would offer better component organization, a single HTML file simplifies deployment and eliminates build steps — appropriate for a research prototype.

2. **Groq over OpenAI**: Groq's free tier provides access to Llama 3.3 70B with sub-second latency on their custom LPU hardware. This eliminates API costs while maintaining model quality comparable to commercial alternatives.

3. **Edge-TTS over commercial TTS**: Microsoft's Edge-TTS is free, requires no API key, and runs locally. While commercial solutions (ElevenLabs, Azure) offer superior voice quality, Edge-TTS provides adequate naturalness for research purposes.

4. **JSON persistence over database**: For a research study with 10–15 sessions, JSON files provide simpler debugging and data export compared to a database system. Each session file is self-contained and human-readable.

5. **Sequential pipeline over parallel**: Each stage depends on the previous stage's output (questions depend on gaps, scoring depends on questions). This sequential dependency is inherent to the interview process and cannot be parallelized.
