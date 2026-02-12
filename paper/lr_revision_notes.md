
# LR Revision Notes (for tomorrow)

## Problem
The current LR was written for a multimodal vision+audio system.
The actual system is voice-only with gap analysis + evidence scoring.
The LR must be rewritten to match.

## Current LR Sections (WRONG)
1. Multimodal Fusion in HRM — talks about video, facial landmarks
2. Hybrid Computing — talks about Edge-Cloud, local GPU
3. Behavioral AI — talks about gaze, micro-expressions, Qwen2.5-VL
4. Democratization — KEEP (still relevant)
5. Research Gap — promises vision features we don't have

## New LR Sections (CORRECT)
1. AI-Assisted Recruitment Tools (HireVue, MyInterview, existing tools)
2. NLP-Based Candidate Assessment (LLMs for evaluation, structured scoring)
3. Transparency in AI Hiring (explainability, evidence-based decisions, bias)
4. Open-Source AI Democratization (KEEP, update refs)
5. Research Gap — reframe:
   - Gap 1: No system does CV-JD gap analysis → personalized questions
   - Gap 2: Existing AI interviewers score without evidence/justification
   - Gap 3: No adaptive follow-up based on real-time scoring

## Actual System Contributions
1. Gap-driven question generation (CV vs JD → targeted questions)
2. Evidence-grounded scoring (every score has a transcript quote)
3. Adaptive follow-up protocol (max 1 per question, score-triggered)
4. Model-agnostic architecture (swap LLMs without changing logic)

## Keep These Citations
- Naim et al. 2015 (early AI hiring — good historical context)
- Qwen Team 2024 (open-source models — still relevant)
- Lepp & Smith 2025 (Global South democratization — still relevant)

## Need New Citations On
- AI interview platforms (HireVue, Pymetrics)
- LLM evaluation/scoring (structured output, rubric-based)
- Explainable AI in HR (transparency, GDPR, bias auditing)
- Gap analysis in recruitment
