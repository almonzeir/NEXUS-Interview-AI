<p align="center">
  <h1 align="center">NEXUS</h1>
  <p align="center"><strong>Automated Competency Assessment System</strong></p>
  <p align="center">
    An evidence-grounded, adaptive AI interview agent for automated candidate screening.<br/>
    Built for research — designed for real-world HR evaluation.
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/LLM-Llama_3.3_70B-7C3AED" />
  <img src="https://img.shields.io/badge/STT-Whisper_V3-FF6F00" />
  <img src="https://img.shields.io/badge/TTS-Edge--TTS-0078D4" />
  <img src="https://img.shields.io/badge/License-Research-gray" />
</p>

---

## 📌 What is NEXUS?

NEXUS is an **AI-powered screening interview system** that autonomously conducts voice-based interviews with candidates. Unlike generic chatbot interviewers, NEXUS uses a novel **gap-driven assessment pipeline**:

1. **Gap Analysis** — Compares the candidate's CV against the Job Description to identify skill matches, gaps, and areas requiring investigation.
2. **Adaptive Question Generation** — Generates personalized interview questions that target the identified gaps, not generic templates.
3. **Evidence-Grounded Scoring** — Every score (0–5) is justified with a **direct quote** from the candidate's transcript, ensuring full transparency.
4. **Structured Assessment Report** — Produces a comprehensive evaluation with per-question evidence chains, dimension scores, and a hiring recommendation.

> **Research Focus:** This system is developed as part of a Final Year Project investigating whether LLM-based interviewers can achieve scoring consistency comparable to human HR evaluators.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CANDIDATE                            │
│                    (Voice via Browser)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │ Audio (WebM)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    NEXUS SERVER (FastAPI)                    │
│                                                             │
│  ┌─────────┐    ┌──────────────┐    ┌─────────────────┐    │
│  │ Whisper  │───▶│  Llama 3.3   │───▶│   Edge-TTS      │    │
│  │ ASR V3   │    │  70B (Groq)  │    │   (Microsoft)   │    │
│  │ (Speech  │    │  (Reasoning, │    │   (Natural      │    │
│  │  to Text)│    │   Scoring,   │    │    Speech)      │    │
│  └─────────┘    │   Questions) │    └─────────────────┘    │
│                  └──────────────┘                            │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              INTERVIEW ENGINE                         │   │
│  │  CV Parser → JD Parser → Gap Analysis → Questions    │   │
│  │  → Scoring (4 dimensions) → Follow-up Logic          │   │
│  │  → Report Generation → Session Persistence           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- A free [Groq API Key](https://console.groq.com)

### Installation

```bash
# Clone the repository
git clone https://github.com/almonzeir/NEXUS-Interview-AI.git
cd NEXUS-Interview-AI

# Install dependencies
pip install -r requirements.txt

# Set your API key
echo GROQ_API_KEY=your_key_here > .env

# Run the server
python nexus_server.py
```

Open `http://localhost:8000` in your browser.

---

## 📋 How It Works

### Step 1: Setup
Paste the candidate's **CV** and the **Job Description** into the setup screen. Click "Analyze & Initialize."

The system will:
- Extract structured data from both documents
- Compare skills, experience, and qualifications
- Identify **matched skills**, **missing skills**, and **probe areas**
- Generate 6–8 targeted interview questions

### Step 2: Interview
Click **"Begin Interview"** and use the **Record** button (or press `Space`) to speak.

The system will:
- Transcribe your speech using Whisper V3
- Score each response on 4 dimensions (Relevance, Depth, Competency, Communication)
- Ask adaptive follow-ups if answers are vague (max 1 follow-up per question)
- Display real-time scores in the evaluation sidebar

### Step 3: Assessment Report
Click **"Assessment Report"** to generate a structured evaluation including:
- Overall competency score
- Per-dimension breakdowns
- Evidence quotes for every score
- AI-generated hiring recommendation (Hire / Consider / Reject)
- Strengths and areas for development

---

## 🔬 Scoring Rubric

Each response is scored 0–5 on four dimensions:

| Dimension | What It Measures |
|---|---|
| **Relevance** | Does the answer directly address the question asked? |
| **Depth** | Are there concrete examples, metrics, or STAR-method stories? |
| **Competency** | Does the answer demonstrate the target skill? |
| **Communication** | Is the response clear, structured, and professional? |

> Every score includes a **direct transcript quote** as evidence — no black-box scoring.

---

## 📁 Project Structure

```
NEXUS-Interview-AI/
├── nexus_server.py          # FastAPI backend (main server)
├── nexus_ui.html            # Research dashboard UI
├── nexus_core/
│   ├── config.py            # Research parameters & model config
│   ├── engine.py            # Core interview logic (modular)
│   └── services/            # Service modules
├── paper/
│   ├── methodology.md       # Research methodology draft
│   └── lr_revision_notes.md # Literature review notes
├── requirements.txt         # Python dependencies
├── Procfile                 # Railway deployment config
├── runtime.txt              # Python version specification
└── .gitignore               # Security (excludes .env, sessions)
```

---

## 🧪 Research Evaluation

This system is evaluated through a comparative study:

1. **Mock interviews** are conducted with volunteer candidates across multiple job roles.
2. The AI scores each response using the 4-dimension rubric.
3. An independent **HR evaluator** scores the same transcripts (blind — without seeing AI scores).
4. Agreement is measured using:
   - Mean Absolute Error (MAE)
   - Pearson Correlation Coefficient (r)
   - Cohen's Kappa (κ)

---

## ⚙️ Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Backend | Python 3.11 / FastAPI | API routing, session management |
| Speech-to-Text | Whisper Large V3 (Groq) | Candidate voice transcription |
| LLM | Llama 3.3 70B (Groq) | Reasoning, scoring, question generation |
| Text-to-Speech | Microsoft Edge-TTS | Natural voice responses |
| Frontend | HTML5 / CSS / JavaScript | Interview dashboard & report |

---

## 🌐 Deployment

### Railway (Recommended)
1. Push this repo to GitHub
2. Connect to [Railway.app](https://railway.app)
3. Add `GROQ_API_KEY` as an environment variable
4. Deploy — Railway auto-detects the `Procfile`

---

## 📄 Citation

If you use this system in your research:

```
@software{nexus_acas_2025,
  title   = {NEXUS: An Evidence-Grounded Adaptive Interview System},
  author  = {Almonzeir},
  year    = {2026},
  url     = {https://github.com/almonzeir/NEXUS-Interview-AI}
}
```

---

## 📜 License

This project is developed for academic research purposes.

---

<p align="center">
  <sub>Built with ☕ at 4 AM — NEXUS Research Team</sub>
</p>
