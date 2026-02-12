import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ["GROQ_API_KEY"] = "gsk_test_key_for_unit_tests"

from nexus_core.structs import CVAnalysis, JDAnalysis, GapAnalysis, Question, AnswerScore, ScoreDetail, RubricScores

class TestAsyncFlow(unittest.TestCase):
    def setUp(self):
        from nexus_core.orchestrator import SessionManager
        SessionManager._sessions = {}

    @patch('nexus_core.orchestrator.llm_gateway')
    def test_setup_flow(self, mock_llm):
        from nexus_core.orchestrator import orchestrator, SessionManager

        mock_cv = CVAnalysis(name="Test Candidate", skills=["Python"], experience_years=5)
        mock_jd = JDAnalysis(title="Software Engineer", required_skills=["Python", "FastAPI"])
        mock_gap = GapAnalysis(match_score=90, matched_skills=["Python"], missing_skills=[], probe_areas=[])

        async def side_effect(prompt, context, model_class):
            if model_class == CVAnalysis:
                return mock_cv
            if model_class == JDAnalysis:
                return mock_jd
            if model_class == GapAnalysis:
                return mock_gap
            if "QuestionList" in str(model_class):
                q1 = Question(
                    id=1, question="Q1", target_area="Python", category="technical",
                    rubric_focus="Skills", follow_up_hint="Hint"
                )
                return model_class(questions=[q1])
            return None

        mock_llm.generate_structured = AsyncMock(side_effect=side_effect)

        async def run_test():
            session = SessionManager.create_session()
            result = await orchestrator.analyze_candidate(session.id, "CV Text", "JD Text")
            self.assertEqual(session.status, "ready")
            self.assertEqual(session.cv_analysis.name, "Test Candidate")
            self.assertEqual(len(session.questions), 1)

        asyncio.run(run_test())

    @patch('nexus_core.orchestrator.llm_gateway')
    def test_interview_flow(self, mock_llm):
        from nexus_core.orchestrator import orchestrator, SessionManager

        session = SessionManager.create_session()
        session.status = "ready"
        session.questions = [
            Question(id=1, question="Q1", target_area="A", category="technical", rubric_focus="F", follow_up_hint="H"),
            Question(id=2, question="Q2", target_area="B", category="technical", rubric_focus="F", follow_up_hint="H")
        ]
        session.current_question_index = 0

        # Updated to include all fields for RubricScores
        scores_obj = RubricScores(
            relevance=ScoreDetail(score=5, evidence="E", reasoning="R"),
            depth=ScoreDetail(score=4, evidence="E", reasoning="R"),
            competency=ScoreDetail(score=5, evidence="E", reasoning="R"),
            communication=ScoreDetail(score=4, evidence="E", reasoning="R")
        )

        mock_score = AnswerScore(
            question_id=1, question_text="Q1", answer_text="Ans",
            scores=scores_obj,
            average_score=4.5
        )

        async def side_effect(prompt, context, model_class=None):
            if model_class == AnswerScore:
                return mock_score
            return "Next Question Text"

        mock_llm.generate_structured = AsyncMock(return_value=mock_score)
        mock_llm.generate_text = AsyncMock(return_value="Next Question Text")

        async def run_test():
            next_q, complete = await orchestrator.process_answer(session.id, "My Answer")
            self.assertEqual(session.current_question_index, 1)
            self.assertFalse(complete)
            self.assertEqual(len(session.scores), 1)
            self.assertEqual(session.scores[0].average_score, 4.5)

        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
