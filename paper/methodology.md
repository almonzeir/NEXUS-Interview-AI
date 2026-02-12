
# 3. Methodology

## 3.1 Overview

This study proposes NEXUS, an Automated Competency Assessment System (ACAS) that conducts adaptive, voice-based screening interviews. Unlike conventional AI interview tools that rely on generic question banks, NEXUS implements a four-phase pipeline that personalises the interview to each candidate–role combination through automated gap analysis between the candidate's curriculum vitae (CV) and the job description (JD).

The core research contribution is the **evidence-grounded scoring mechanism**: every score assigned to a candidate's response is accompanied by a direct quotation from the transcript, ensuring transparency and auditability of the AI's evaluation.

Figure X illustrates the overall system architecture.

---

## 3.2 System Architecture

NEXUS is implemented as a client–server web application comprising three components:

| Component | Technology | Role |
|-----------|-----------|------|
| Frontend | HTML5 / JavaScript | Voice capture, real-time transcript display, assessment report rendering |
| Backend | Python 3.11 / FastAPI | Interview orchestration, API routing, session management |
| AI Services | Groq Cloud API | Speech-to-text (Whisper), reasoning (Llama 3.3 70B), text-to-speech (Edge-TTS) |

### 3.2.1 Model Selection Rationale

The system adopts a **model-agnostic architecture**, where AI capabilities are accessed through standardised API calls rather than tightly coupled to a specific model. For this study, the following models were selected:

- **Speech-to-Text:** OpenAI Whisper Large V3, accessed via Groq's inference endpoint. Whisper was chosen for its state-of-the-art accuracy across accents and its open-source availability (MIT License), which supports reproducibility.

- **Large Language Model:** Meta Llama 3.3 70B Versatile, a 70-billion parameter instruction-tuned model. This model was selected for its strong performance on reasoning and structured output tasks, its production-grade stability on the Groq platform, and its open-source licence (Llama Community License), enabling academic reproducibility.

- **Text-to-Speech:** Microsoft Edge-TTS (en-US-GuyNeural voice) was used to generate natural-sounding spoken responses. The slightly increased speech rate (+10%) was chosen to maintain conversational flow during the interview.

The model-agnostic design allows future researchers to substitute alternative models (e.g., GPT-4, Qwen3, Gemini) without modifying the core interview logic, facilitating cross-model comparison studies.

---

## 3.3 Interview Pipeline

The NEXUS interview pipeline consists of four sequential phases:

### Phase 1: Gap Analysis (Pre-Interview)

Before the interview begins, the system performs an automated gap analysis between the candidate's CV and the target JD. This phase involves three sub-steps:

**Step 1a — CV Parsing.** The candidate's CV text is submitted to the LLM with a structured extraction prompt. The model returns a JSON object containing:
- Technical skills (list)
- Years of experience
- Work history (title, company, duration, key achievements)
- Education (degree, institution, year)
- Projects and tools

**Step 1b — JD Parsing.** The job description is similarly parsed to extract:
- Required and preferred skills
- Minimum experience requirement
- Key responsibilities
- Required soft skills

**Step 1c — Comparative Gap Identification.** The extracted CV and JD structures are compared by the LLM to produce:
- **Match score** (0–100): overall alignment between candidate and role
- **Matched skills**: skills present in both CV and JD
- **Missing skills**: JD requirements absent from the CV
- **Probe areas**: ambiguities or weaknesses that require deeper investigation during the interview, each assigned a priority level (high/medium/low)

This gap analysis directly informs question generation, ensuring that interview time is allocated to areas of greatest uncertainty rather than spent on already-verified competencies.

### Phase 2: Adaptive Question Generation

Based on the gap analysis output, the LLM generates 6–8 targeted interview questions. Each question is structured with the following metadata:

```
{
  "id": integer,
  "question": "The question text (conversational tone)",
  "type": "behavioral | technical | situational",
  "target_competency": "The specific skill or gap being probed",
  "rubric_guide": "Description of what a strong answer demonstrates",
  "follow_up_hint": "A follow-up question if the initial answer is vague"
}
```

The question generation follows a deliberate strategy:
1. **Question 1:** Warm greeting and self-introduction (rapport building)
2. **Questions 2–3:** Verify claimed strengths from the CV (competency confirmation)
3. **Questions 4–6:** Probe identified gaps and weaknesses (gap investigation)
4. **Final question:** Open floor for candidate questions (candidate agency)

This structure mirrors established HR interviewing best practices while ensuring systematic coverage of the gap analysis findings.

### Phase 3: Evidence-Grounded Scoring

Each candidate response is evaluated across four rubric dimensions on a 0–5 scale:

| Dimension | Definition | Score 0 | Score 5 |
|-----------|-----------|---------|---------|
| **Relevance** | Directness in answering the specific question | Completely off-topic | Directly and fully addresses the question |
| **Depth** | Presence of concrete examples and quantitative impact | No specifics given | Rich, detailed examples using STAR method |
| **Competency** | Demonstration of the target skill or domain expertise | No evidence of skill | Strong, clear evidence of expertise |
| **Communication** | Clarity, structure, and professional delivery | Incoherent or disorganised | Exceptionally clear and well-structured |

**Evidence requirement.** The scoring prompt mandates that every score must be accompanied by:
1. A **direct quotation** from the candidate's answer serving as evidence
2. A **reasoning statement** explaining why the quoted content warrants the assigned score

This evidence-grounding mechanism serves two purposes:
- **Transparency:** Evaluators (and candidates) can trace each score back to specific utterances
- **Validation:** Human reviewers can assess whether the AI's scoring logic is sound by examining the evidence chain

**Scoring constraints:**
- Scores are based on **content and substance only**; accent, grammar errors, and speaking style are explicitly excluded from evaluation
- The system does not penalise non-native English speakers for linguistic errors unrelated to the assessed competency

### Phase 4: Adaptive Follow-Up Protocol

After scoring each response, the system determines whether a follow-up question is needed:

- If the **average score < 3.0** and no follow-up has been asked for the current question, the system generates a natural follow-up based on the pre-defined `follow_up_hint`
- Each question receives a **maximum of one follow-up** to avoid interrogation loops
- If the candidate cannot elaborate after the follow-up, the system moves to the next question

This adaptive behaviour ensures that the interview responds to the candidate's performance in real-time while maintaining a professional and non-adversarial tone.

---

## 3.4 Report Generation

Upon completion of all questions, the system generates a structured assessment report containing:

1. **Quantitative Metrics:**
   - Per-question scores across all four dimensions
   - Average scores per dimension
   - Overall competency score (mean of all dimension averages)

2. **Qualitative Analysis:**
   - AI-generated hiring recommendation (Hire / Consider / Reject)
   - Executive summary of candidate performance
   - Key strengths and areas for development
   - Per-question evidence chains (question → answer → quote → score → reasoning)

3. **Research Metadata:**
   - Session identifier and timestamp
   - Model versions used (STT, LLM, TTS)
   - Per-turn response latencies (STT time, LLM inference time, TTS time)
   - Full conversation transcript

All session data is persisted as JSON files for subsequent analysis.

---

## 3.5 Evaluation Design

To evaluate the effectiveness of the proposed system, a comparative study was conducted between AI-generated scores and independent human evaluations.

### 3.5.1 Participants

- **Mock candidates:** [N] volunteers were recruited to participate in simulated screening interviews across [X] different job roles.
- **Human evaluator:** An HR student with [X years/months] of academic training in human resource management independently scored the same interview transcripts using the identical four-dimension rubric.

### 3.5.2 Procedure

1. Each candidate was assigned a job role and provided a CV (either their own or a prepared sample).
2. The NEXUS system conducted the interview autonomously.
3. The generated transcript and per-question scoring were saved.
4. The human evaluator received only the **transcript** (without AI scores) and scored each response using the same rubric (Relevance, Depth, Competency, Communication; 0–5 each).
5. AI scores and human scores were compared.

### 3.5.3 Metrics

The following metrics were used to assess system performance:

- **Mean Absolute Error (MAE):** Average difference between AI and human scores per dimension
- **Pearson Correlation Coefficient (r):** Strength of linear relationship between AI and human scores
- **Cohen's Kappa (κ):** Inter-rater agreement, accounting for chance agreement
- **Response Latency:** End-to-end time from candidate speech to system response (STT + LLM + TTS)

---

## 3.6 Ethical Considerations

The following ethical safeguards were implemented:

- All participants provided informed consent before mock interviews
- No personally identifiable information (PII) was transmitted to or stored by external APIs beyond the interview session
- The scoring rubric explicitly prohibits bias based on accent, dialect, or grammatical errors
- The system is positioned as a **screening assistance tool**, not a replacement for human decision-making; final hiring decisions remain with human evaluators
- All AI-generated recommendations are accompanied by evidence trails for human review

