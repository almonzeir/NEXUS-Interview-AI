"""
NEXUS Interview Orchestrator
============================
Manages the lifecycle of interview sessions, including:
- Parallel CV/JD Analysis
- Gap Analysis & Question Generation
- Interview Flow Control (Q&A Loop)
- Scoring & Adaptive Follow-ups
- Persistent Storage
"""

import asyncio
import logging
import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from datetime import datetime

from .structs import (
    InterviewSession, CVAnalysis, JDAnalysis, GapAnalysis,
    Question, AnswerScore, FinalReport, Recommendation,
    EyeContactMetric
)
from .llm_gateway import llm_gateway

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path("research_data/sessions")
DATA_DIR.mkdir(parents=True, exist_ok=True)

class SessionManager:
    """Session storage with JSON persistence."""
    _sessions: Dict[str, InterviewSession] = {}

    @classmethod
    def load_all_sessions(cls):
        """Load sessions from disk on startup."""
        for file in DATA_DIR.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                # Use strict validation, but allow partial data if schema evolved
                # Ideally, we should use model_validate, but for robustness:
                session = InterviewSession.model_validate(data)
                cls._sessions[session.id] = session
            except Exception as e:
                logger.warning(f"Failed to load session {file}: {e}")

    @classmethod
    def save_session(cls, session: InterviewSession):
        """Persist session to disk."""
        path = DATA_DIR / f"{session.id}.json"
        path.write_text(session.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def create_session(cls) -> InterviewSession:
        session = InterviewSession()
        cls._sessions[session.id] = session
        cls.save_session(session)
        return session

    @classmethod
    def get_session(cls, session_id: str) -> Optional[InterviewSession]:
        return cls._sessions.get(session_id)

    @classmethod
    def list_sessions(cls):
        return cls._sessions.values()

# Load sessions immediately
SessionManager.load_all_sessions()


class InterviewOrchestrator:
    """
    The Brain of NEXUS. Coordinates data flow between API, LLM, and Session.
    """

    @staticmethod
    async def analyze_candidate(session_id: str, cv_text: str, jd_text: str) -> Dict:
        """
        Step 1: Parallel Analysis of CV and JD, followed by Gap Analysis.
        """
        session = SessionManager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        session.cv_text = cv_text
        session.jd_text = jd_text
        session.status = "setup"
        SessionManager.save_session(session)

        # 1. Parallel Execution: CV Parsing & JD Parsing
        logger.info(f"Session {session_id}: Starting parallel analysis...")

        async def parse_cv():
            prompt = "Extract structured data from this CV:"
            return await llm_gateway.generate_structured(prompt, cv_text, CVAnalysis)

        async def parse_jd():
            prompt = "Extract structured requirements from this Job Description:"
            return await llm_gateway.generate_structured(prompt, jd_text, JDAnalysis)

        try:
            cv_data, jd_data = await asyncio.gather(parse_cv(), parse_jd())
            session.cv_analysis = cv_data
            session.jd_analysis = jd_data
            SessionManager.save_session(session)
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise RuntimeError(f"Failed to analyze documents: {str(e)}")

        # 2. Sequential Execution: Gap Analysis (Depends on CV & JD)
        logger.info(f"Session {session_id}: Analyzing gaps...")

        gap_prompt = """Compare the candidate's CV against the Job Description.
Identify matches, gaps, and areas to probe. Be critical but fair.
"""
        user_content = f"CV: {cv_data.model_dump_json()}\nJD: {jd_data.model_dump_json()}"

        try:
            gap_data = await llm_gateway.generate_structured(gap_prompt, user_content, GapAnalysis)
            session.gap_analysis = gap_data
            SessionManager.save_session(session)
        except Exception as e:
            logger.error(f"Gap analysis failed: {e}")
            raise RuntimeError(f"Failed to analyze gaps: {str(e)}")

        # 3. Question Generation
        logger.info(f"Session {session_id}: Generating questions...")

        # We need a list of questions, so we define a wrapper model
        from pydantic import BaseModel
        class QuestionList(BaseModel):
            questions: List[Question]

        q_prompt = """Generate 6-8 targeted interview questions based on the gap analysis.
Strategy:
1. Warm up (Introduction)
2. Verify strengths (Matched skills)
3. Probe weaknesses (Missing skills/Gaps)
4. Closing (Opportunity for candidate to ask questions)

Ensure questions are conversational and clearly linked to a gap or competency."""

        q_user_content = f"Gap Analysis: {gap_data.model_dump_json()}"

        try:
            q_list = await llm_gateway.generate_structured(q_prompt, q_user_content, QuestionList)
            session.questions = q_list.questions
            session.status = "ready"
            SessionManager.save_session(session)
        except Exception as e:
            logger.error(f"Question generation failed: {e}")
            raise RuntimeError(f"Failed to generate questions: {str(e)}")

        return {
            "cv": session.cv_analysis,
            "jd": session.jd_analysis,
            "gaps": session.gap_analysis,
            "questions": session.questions
        }

    @staticmethod
    async def get_next_question(session_id: str) -> Optional[str]:
        """
        Get the text of the next question to ask.
        """
        session = SessionManager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        if session.current_question_index >= len(session.questions):
            session.status = "completed"
            SessionManager.save_session(session)
            return None

        q = session.questions[session.current_question_index]
        return q.question

    @staticmethod
    async def process_answer(session_id: str, transcript: str, eye_metrics: List[EyeContactMetric] = None) -> Tuple[str, bool]:
        """
        Process the candidate's answer:
        1. Log Eye Contact metrics.
        2. Score the answer (Async).
        3. Decide on follow-up.
        4. Return the next response (Follow-up or Next Question).
        """
        session = SessionManager.get_session(session_id)
        if not session or session.status == "completed":
            return "Interview is complete. Thank you.", True

        # 0. Log Eye Metrics
        if eye_metrics:
            session.eye_contact_logs.extend(eye_metrics)
            # Simple avg confidence check
            avg_conf = sum(m.confidence for m in eye_metrics) / len(eye_metrics) if eye_metrics else 0
            logger.info(f"Session {session_id}: Eye Contact Avg Confidence: {avg_conf:.2f}")

        current_q = session.questions[session.current_question_index]

        # 1. Score Answer
        logger.info(f"Session {session_id}: Scoring answer to Q{current_q.id}...")

        score_prompt = """Score the candidate's answer based on the rubric.
You MUST provide a direct quote as evidence for every score.
Think step-by-step in the 'chain_of_thought' field.
Rubric Dimensions: Relevance, Depth, Competency, Communication.
"""

        user_content = f"""
Question: {current_q.question}
Target Area: {current_q.target_area}
Rubric Focus: {current_q.rubric_focus}

Candidate Answer: "{transcript}"
"""

        try:
            score_data = await llm_gateway.generate_structured(score_prompt, user_content, AnswerScore)
            # Hydrate fields not filled by LLM
            score_data.question_id = current_q.id
            score_data.question_text = current_q.question
            score_data.answer_text = transcript

            session.scores.append(score_data)
            SessionManager.save_session(session)

            # 2. Check for Follow-up (Adaptive Logic)
            # Condition: Score < 3 AND haven't followed up on this question yet
            if (score_data.average_score < 3.0 and
                score_data.needs_follow_up and
                current_q.id not in session.followed_up_questions):

                logger.info(f"Session {session_id}: Triggering follow-up for Q{current_q.id}")
                session.followed_up_questions.append(current_q.id)
                SessionManager.save_session(session)

                follow_up_prompt = f"The candidate gave a weak answer to: '{current_q.question}'. Ask a polite but probing follow-up question. Hint: {current_q.follow_up_hint or 'Ask for a specific example.'}"
                follow_up_q = await llm_gateway.generate_text("You are an interviewer.", follow_up_prompt, temperature=0.7)

                return follow_up_q, False

        except Exception as e:
            logger.error(f"Scoring/Follow-up failed: {e}")
            # Non-blocking error - continue to next question
            pass

        # 3. Move to Next Question
        session.current_question_index += 1
        SessionManager.save_session(session)

        next_q_text = await InterviewOrchestrator.get_next_question(session_id)

        if next_q_text:
            # Transition Logic (Optional: make it natural)
            return next_q_text, False
        else:
            return "Thank you for your time. The interview is now complete.", True

    @staticmethod
    async def generate_final_report(session_id: str) -> FinalReport:
        """
        Compile all data into a structured report.
        """
        session = SessionManager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        logger.info(f"Session {session_id}: Generating final report...")

        # Calculate Aggregates
        scores = session.scores
        rubric_avg = {
            "relevance": 0.0, "depth": 0.0, "competency": 0.0, "communication": 0.0, "overall": 0.0
        }

        if scores:
            for dim in ["relevance", "depth", "competency", "communication"]:
                # Access the ScoreDetail object from the RubricScores model
                total = sum(getattr(s.scores, dim).score for s in scores)
                rubric_avg[dim] = round(total / len(scores), 2)
            rubric_avg["overall"] = round(sum(s.average_score for s in scores) / len(scores), 2)

        # Generate Recommendation
        rec_prompt = "Review the interview scores and generate a hiring recommendation."
        rec_context = f"""
Candidate: {session.cv_analysis.name}
Role: {session.jd_analysis.title}
Scores: {rubric_avg}
Detailed Scores: {[s.model_dump_json() for s in scores]}
"""
        recommendation = await llm_gateway.generate_structured(rec_prompt, rec_context, Recommendation)

        report = FinalReport(
            session_id=session.id,
            generated_at=datetime.now(),
            candidate=session.cv_analysis,
            job=session.jd_analysis,
            gap_analysis=session.gap_analysis,
            interview_duration="N/A", # Calc later
            total_questions=len(session.questions),
            questions_answered=len(session.scores),
            rubric_scores=rubric_avg,
            per_question_scores=session.scores,
            recommendation=recommendation,
            transcript=session.conversation_history,
            response_latencies=session.timings,
            model_info={"provider": "Groq", "model": llm_gateway.primary_model}
        )

        return report

orchestrator = InterviewOrchestrator()
