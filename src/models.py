from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ScoreBreakdown(BaseModel):
    ai_project_depth: int = Field(0, description="Score for AI, agentic, RAG project depth (0-40)")
    python_backend: int = Field(0, description="Score for Python and backend engineering (0-30)")
    cloud_fullstack: int = Field(0, description="Score for cloud, Docker, deployment & supporting full stack (0-15)")
    github: int = Field(0, description="Score for public GitHub activity & repositories (0-10)")
    engineering_depth: int = Field(0, description="Score for engineering depth signals e.g. tests, caching, arch (0-5)")

class CandidateResult(BaseModel):
    rank: Optional[int] = Field(None, description="1-based ranking for eligible candidates, null if ineligible")
    candidate_name: str = Field(..., description="Candidate name")
    eligible: bool = Field(..., description="True if passes both Python and AI hard filters")
    rejection_reasons: List[str] = Field(default_factory=list, description="Explicit reasons if rejected")
    total_score: int = Field(0, description="Final score out of 100")
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown, description="Category-wise score breakdown")
    matched_skills: List[str] = Field(default_factory=list, description="Verified skills extracted from resume")
    project_summary: str = Field("", description="Evidence-backed summary of candidate projects")
    github_summary: str = Field("", description="Summary of GitHub enrichment results")
    strengths: List[str] = Field(default_factory=list, description="Key candidate strengths")
    concerns: List[str] = Field(default_factory=list, description="Key flags or missing signals")
    file_name: Optional[str] = Field(None, description="Source resume filename")
    email: Optional[str] = Field(None, description="Extracted candidate email")
    github_url: Optional[str] = Field(None, description="Extracted candidate GitHub profile URL")

class BatchSummary(BaseModel):
    total_resumes: int = Field(0, description="Total resumes found in input directory")
    successfully_parsed: int = Field(0, description="Count of resumes successfully parsed")
    eligible: int = Field(0, description="Count of candidates passing hard eligibility")
    rejected: int = Field(0, description="Count of candidates rejected by hard filters")
    failed_unreadable: int = Field(0, description="Count of malformed/unreadable resumes")

class ScreeningResponse(BaseModel):
    batch_summary: BatchSummary
    ranked_candidates: List[CandidateResult]
    rejected_candidates: List[CandidateResult]

class ParsedResume(BaseModel):
    file_path: str
    file_name: str
    raw_text: str
    candidate_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    github_url: Optional[str] = None
    github_username: Optional[str] = None
    linkedin_url: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    sections: Dict[str, str] = Field(default_factory=dict)
