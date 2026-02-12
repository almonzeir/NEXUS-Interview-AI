"""
NEXUS Core Data Structures
==========================
Pydantic models for strict type validation and structured LLM outputs.
"""

from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

# ─── CV & JD ANALYSIS MODELS ────────────────────────────────────────────────

class Experience(BaseModel):
    title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company name")
    duration: str = Field(..., description="Duration of employment")
    highlights: List[str] = Field(default_factory=list, description="Key achievements or responsibilities")

class Education(BaseModel):
    degree: str = Field(..., description="Degree obtained")
    institution: str = Field(..., description="University or institution")
    year: str = Field(..., description="Year of graduation")

class CVAnalysis(BaseModel):
    name: Optional[str] = Field(None, description="Candidate's full name")
    skills: List[str] = Field(default_factory=list, description="List of technical and soft skills")
    experience_years: float = Field(0.0, description="Total years of professional experience")
    experiences: List[Experience] = Field(default_factory=list, description="Work history")
    education: List[Education] = Field(default_factory=list, description="Educational background")
    projects: List[str] = Field(default_factory=list, description="Notable projects")
    tools: List[str] = Field(default_factory=list, description="Tools and technologies used")
    summary: str = Field("", description="Brief professional summary")

class JDAnalysis(BaseModel):
    title: str = Field(..., description="Job title")
    company: Optional[str] = Field(None, description="Company name")
    required_skills: List[str] = Field(default_factory=list, description="Mandatory skills")
    preferred_skills: List[str] = Field(default_factory=list, description="Nice-to-have skills")
    experience_required: str = Field("", description="Experience requirement text")
    education_required: str = Field("", description="Education requirement text")
    key_responsibilities: List[str] = Field(default_factory=list, description="Core duties")
    soft_skills: List[str] = Field(default_factory=list, description="Required soft skills")
    summary: str = Field("", description="Brief role summary")

# ─── GAP ANALYSIS MODELS ────────────────────────────────────────────────────

class ProbeArea(BaseModel):
    area: str = Field(..., description="The specific skill or gap to probe")
    reason: str = Field(..., description="Why this needs investigation")
    priority: Literal["high", "medium", "low"] = Field("medium", description="Importance of this probe")

class GapAnalysis(BaseModel):
    match_score: float = Field(..., ge=0, le=100, description="Overall alignment score (0-100)")
    matched_skills: List[str] = Field(default_factory=list, description="Skills present in both CV and JD")
    missing_skills: List[str] = Field(default_factory=list, description="Required skills missing from CV")
    experience_gap: str = Field("None", description="Analysis of experience gap")
    education_match: bool = Field(True, description="Whether education requirements are met")
    strengths: List[str] = Field(default_factory=list, description="Candidate's key strengths")
    concerns: List[str] = Field(default_factory=list, description="Potential red flags or concerns")
    probe_areas: List[ProbeArea] = Field(default_factory=list, description="Areas requiring interview verification")

# ─── INTERVIEW CONTENT MODELS ───────────────────────────────────────────────

class Question(BaseModel):
    id: int = Field(..., description="Question sequence number")
    question: str = Field(..., description="The actual question text to speak")
    target_area: str = Field(..., description="The competency or gap being assessed")
    category: Literal["technical", "behavioral", "situational", "competency", "introduction", "closing"] = Field(..., description="Type of question")
    rubric_focus: str = Field(..., description="What a strong answer should demonstrate")
    follow_up_hint: Optional[str] = Field(None, description="Hint for generating a follow-up if needed")

class ScoreDetail(BaseModel):
    score: int = Field(..., ge=0, le=5, description="Score from 0 to 5")
    evidence: str = Field(..., description="Direct quote from the candidate's answer")
    reasoning: str = Field(..., description="Explanation for the assigned score")

class RubricScores(BaseModel):
    relevance: ScoreDetail = Field(..., description="Relevance to the question")
    depth: ScoreDetail = Field(..., description="Detail and examples provided")
    competency: ScoreDetail = Field(..., description="Skill demonstration")
    communication: ScoreDetail = Field(..., description="Clarity and professionalism")

class AnswerScore(BaseModel):
    question_id: int = Field(..., description="ID of the question answered")
    question_text: str = Field(..., description="The question text")
    answer_text: str = Field(..., description="The candidate's response")
    chain_of_thought: str = Field("", description="LLM's reasoning process")
    scores: RubricScores = Field(..., description="Structured scores across 4 dimensions")
    average_score: float = Field(..., description="Mean of dimension scores")
    needs_follow_up: bool = Field(False, description="Whether a follow-up is recommended")
    follow_up_reason: Optional[str] = Field(None, description="Reason for follow-up")

class Recommendation(BaseModel):
    recommendation: Literal["RECOMMEND", "CONSIDER", "DO NOT RECOMMEND"] = Field(..., description="Hiring recommendation")
    summary: str = Field(..., description="Executive summary")
    strengths: List[str] = Field(default_factory=list, description="Key strengths identified")
    areas_for_development: List[str] = Field(default_factory=list, description="Areas needing improvement")
    hiring_confidence: float = Field(..., ge=0, le=100, description="Confidence in the recommendation")

class FinalReport(BaseModel):
    session_id: str
    generated_at: datetime
    candidate: CVAnalysis
    job: JDAnalysis
    gap_analysis: GapAnalysis
    interview_duration: Optional[str]
    total_questions: int
    questions_answered: int
    rubric_scores: Dict[str, float]
    per_question_scores: List[AnswerScore]
    recommendation: Recommendation
    transcript: List[Dict]
    response_latencies: List[Dict]
    model_info: Dict[str, str]

# ─── SESSION STATE ──────────────────────────────────────────────────────────

class EyeContactMetric(BaseModel):
    timestamp: float
    gaze_on_screen: bool
    confidence: float

class InterviewSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    status: Literal["idle", "setup", "ready", "interviewing", "completed", "error"] = "idle"

    # Input Data
    cv_text: str = ""
    jd_text: str = ""

    # Analysis Data
    cv_analysis: Optional[CVAnalysis] = None
    jd_analysis: Optional[JDAnalysis] = None
    gap_analysis: Optional[GapAnalysis] = None

    # Interview Flow
    questions: List[Question] = Field(default_factory=list)
    current_question_index: int = 0
    conversation_history: List[Dict] = Field(default_factory=list) # Raw chat logs
    scores: List[AnswerScore] = Field(default_factory=list)

    # Metadata
    timings: List[Dict] = Field(default_factory=list)
    models_used: List[str] = Field(default_factory=list)
    followed_up_questions: List[int] = Field(default_factory=list) # IDs of questions we've already followed up on

    # Camera / Eye Tracking
    eye_contact_logs: List[EyeContactMetric] = Field(default_factory=list)
