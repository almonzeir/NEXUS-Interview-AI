
# ═════════════════════════════════════════════════════════════════════════
# NEXUS AI ENGINE
# Core Logic for Interview Gap Analysis and Question Generation
# ═════════════════════════════════════════════════════════════════════════

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from groq import Groq

from .config import GROQ_API_KEY, LLM_MODEL, LLM_TEMP, LLM_MAX_TOKENS

# Setup Research-Grade Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NexusEngine:
    """
    Main engine for the NEXUS specific research methodology:
    1. Parse CV (Structured Extraction)
    2. Parse JD (Requirement Mapping)
    3. Gap Analysis (Comparative Logic)
    4. Adaptive Interview (Dynamic Q&A)
    """

    def __init__(self):
        try:
            self.client = Groq(api_key=GROQ_API_KEY)
            logger.info(f"✅ Research Engine Initialized with model: {LLM_MODEL}")
        except Exception as e:
            logger.critical(f"❌ Failed to initialize Groq client: {e}")
            raise

    # ── LLM WRAPPER ──
    def call_llm(self, messages: list, max_tokens: int = LLM_MAX_TOKENS) -> str:
        """Raw LLM call with research-grade error handling."""
        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                temperature=LLM_TEMP,
                max_tokens=max_tokens,
                top_p=1,
                stream=False
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM Inference Error: {e}")
            return "Internal processing error."

    def call_llm_json(self, messages: list, max_tokens: int = LLM_MAX_TOKENS) -> dict:
        """Structured Output (JSON) wrapper for data extraction."""
        messages[0]["content"] += "\nReturn ONLY valid JSON. No markdown ticks ```json."
        
        raw_text = self.call_llm(messages, max_tokens)
        
        # Cleanup common LLM formatting issues
        cleaned = raw_text.replace("```json", "").replace("```", "").strip()
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON Parse Error: {e}. Raw Output: {cleaned[:100]}...")
            # Fallback: simple dict or retry logic could be here
            return {}

    # ── METHODOLOGY: GAP ANALYSIS ──
    def analyze_resume_gap(self, cv_text: str, jd_text: str) -> dict:
        """
        Phase 1: Determine the gap between Candidate and Requirement.
        This forms the basis for QUESTION GENERATION.
        """
        logger.info("Executing Gap Analysis Protocol...")
        
        # 1. Parse CV structure
        cv_sys = "Extract structured data: name, skills (list), experience (years + list), education, projects."
        cv_data = self.call_llm_json([
            {"role": "system", "content": f"{cv_sys} Return JSON."},
            {"role": "user", "content": cv_text}
        ])
        
        # 2. Parse JD structure
        jd_sys = "Extract structured requirements: title, required_skills (list), preferred_skills, experience_min, responsibilities."
        jd_data = self.call_llm_json([
            {"role": "system", "content": f"{jd_sys} Return JSON."},
            {"role": "user", "content": jd_text}
        ])
        
        # 3. Compare (Gap Analysis)
        gap_sys = """Compare CV vs JD. Identify:
        - match_score (0-100)
        - matched_skills
        - missing_skills
        - probe_areas (ambiguities or weaknesses to test)
        Return JSON."""
        
        gap_data = self.call_llm_json([
            {"role": "system", "content": gap_sys},
            {"role": "user", "content": f"CV: {json.dumps(cv_data)}\nJD: {json.dumps(jd_data)}"}
        ])

        return {
            "cv": cv_data,
            "jd": jd_data,
            "gap": gap_data
        }

    # ── METHODOLOGY: ADAPTIVE QUESTIONING ──
    def generate_interview_script(self, analysis_data: dict) -> list:
        """
        Phase 2: Generate Targeted Questions.
        Questions must probe the IDENTIFIED GAPS.
        """
        logger.info("Generating Adaptive Interview Script...")
        
        sys_prompt = """Generate 6-8 behavioral and technical interview questions based on the candidate's GAP ANALYSIS.
        
        STRATEGY:
        1. Start with a warm introduction.
        2. Verify 2-3 key strengths (competency check).
        3. *Aggressively* probe the identified 'missing_skills' or 'probe_areas'.
        4. End with an open floor.
        
        JSON Format per question:
        {
            "id": 1,
            "question": "text",
            "type": "behavioral/technical",
            "target_competency": "skill name",
            "rubric_guide": "what a good answer looks like",
            "follow_up_hint": "if answer is vague, ask X"
        }
        """
        
        user_prompt = f"Gap Analysis Data: {json.dumps(analysis_data['gap'])}"
        
        result = self.call_llm_json([
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ])
        
        return result.get("questions", [])

    # ── METHODOLOGY: SCORING LOGIC ──
    def score_candidate_response(self, question: dict, answer: str) -> dict:
        """
        Phase 3: Evidence-Based Scoring.
        Scores (0-5) must be justified by EXPLICIT QUOTES from the transcript.
        """
        if len(answer) < 5:
            return {"score": 0, "reasoning": "No answer provided.", "evidence": "N/A"}

        sys_prompt = """Score the response (0-5) on: Relevance, Depth, Competency, Communication.
        CRITICAL: Provide a direct QUOTE from the answer as evidence for each score.
        Reference the 'target_competency' and 'rubric_guide'.
        
        Return JSON:
        {
            "scores": {"relevance": 0, "depth": 0, "competency": 0, "communication": 0},
            "evidence_quote": "exact quote",
            "reasoning": "analysis",
            "follow_up_needed": boolean (true if score < 3)
        }
        """
        
        user_prompt = f"""
        Question: {question['question']}
        Target: {question['target_competency']}
        Rubric Guide: {question['rubric_guide']}
        
        Candidate Answer: "{answer}"
        """
        
        return self.call_llm_json([
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ])

    def generate_final_report(self, session_data: dict) -> dict:
        """Phase 4: Synthesis & Recommendation."""
        logger.info(f"Synthesizing final report for Session {session_data.get('id')}")
        
        sys_prompt = """Act as a Senior Hiring Manager. Review the interview transcript and scores.
        Generate a Hiring Recommendation (Hire / Consider / Reject).
        Justify with key strengths and red flags.
        
        Return JSON:
        {
            "recommendation": "HIRE/CONSIDER/REJECT",
            "summary": "Executive summary",
            "strengths": ["list"],
            "weaknesses": ["list"]
        }
        """
        
        # Calculate quantitative metrics
        scores = [s.get("result", {}).get("scores", {}).get("competency", 0) for s in session_data["history"] if "result" in s]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        transcript_text = "\n".join([f"Q: {q['question']}\nA: {q.get('answer', '')}" for q in session_data["history"]])
        
        qualitative = self.call_llm_json([
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Avg Score: {avg_score:.1f}/5.0\n\nTranscript:\n{transcript_text}"}
        ])
        
        return {
            "quantitative": {"average_competency": avg_score},
            "qualitative": qualitative
        }

# Initializer for easy import
engine = NexusEngine()
