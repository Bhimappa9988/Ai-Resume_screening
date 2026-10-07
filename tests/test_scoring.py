import pytest
from src.scoring import CandidateScorer
from src.models import ParsedResume
from src.llm_adapter import ProjectQualityAssessment

@pytest.fixture
def scorer():
    return CandidateScorer()

def test_score_max_capping(scorer):
    """Ensure total score does not exceed 100 even with exceptional signals across all categories."""
    parsed = ParsedResume(
        file_path="high_profile.pdf",
        file_name="high_profile.pdf",
        raw_text="""
        Projects:
        LangGraph multi-agent orchestration, RAG retrieval system with ChromaDB, vector search, tool calling,
        function calling, evaluation pipeline with Ragas, FastAPI async backend, asyncio, PostgreSQL, SQLAlchemy,
        Redis caching, Celery tasks, Docker containerization, Kubernetes, GCP deployment, React frontend,
        pytest test suite with CI/CD GitHub Actions, rate limiting and observability.
        """,
        candidate_name="Star Candidate",
        skills=["Python", "FastAPI", "LangGraph", "RAG", "PostgreSQL", "Docker", "GCP"],
    )
    github_enrichment = {"score": 10, "status": "success", "summary": "Active contributor"}
    quality_assessment = ProjectQualityAssessment(
        is_thin_wrapper=False,
        penalty_points=0,
        penalty_reason="",
        project_summary="Built comprehensive multi-agent RAG system.",
        key_strengths=["Agent architecture", "FastAPI async", "Cloud deployment"],
        key_concerns=[],
    )

    score, breakdown, strengths, concerns = scorer.score_candidate(
        parsed, github_enrichment, quality_assessment
    )

    assert score <= 100
    assert score >= 80
    assert breakdown.ai_project_depth <= 40
    assert breakdown.python_backend <= 30
    assert breakdown.cloud_fullstack <= 15
    assert breakdown.github <= 10
    assert breakdown.engineering_depth <= 5

def test_thin_wrapper_penalty(scorer):
    """Ensure thin wrapper penalty is properly deducted from total score."""
    parsed = ParsedResume(
        file_path="wrapper_profile.pdf",
        file_name="wrapper_profile.pdf",
        raw_text="""
        Projects:
        Built a simple chatbot using OpenAI API and Python Flask.
        """,
        candidate_name="Wrapper Dev",
        skills=["Python", "Flask", "OpenAI"],
    )
    github_enrichment = {"score": 2, "status": "success", "summary": "Minimal repos"}
    
    # Without penalty
    qa_clean = ProjectQualityAssessment(
        is_thin_wrapper=False,
        penalty_points=0,
        project_summary="Simple bot.",
    )
    score_clean, _, _, _ = scorer.score_candidate(parsed, github_enrichment, qa_clean)

    # With penalty
    qa_penalized = ProjectQualityAssessment(
        is_thin_wrapper=True,
        penalty_points=10,
        penalty_reason="Thin OpenAI API wrapper without retrieval or state.",
        project_summary="Simple bot wrapper.",
    )
    score_penalized, _, _, _ = scorer.score_candidate(parsed, github_enrichment, qa_penalized)

    assert score_penalized == max(0, score_clean - 10)

def test_score_floor(scorer):
    """Ensure score never drops below 0 even with large penalty."""
    parsed = ParsedResume(
        file_path="low.pdf",
        file_name="low.pdf",
        raw_text="Basic python tutorial.",
        candidate_name="Novice",
        skills=["Python"],
    )
    github_enrichment = {"score": 0, "status": "none", "summary": "None"}
    qa = ProjectQualityAssessment(
        is_thin_wrapper=True,
        penalty_points=15,
        penalty_reason="Tutorial project.",
        project_summary="",
    )
    score, _, _, _ = scorer.score_candidate(parsed, github_enrichment, qa)
    assert score >= 0
