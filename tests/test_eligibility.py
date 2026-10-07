import pytest
from src.eligibility import EligibilityChecker
from src.models import ParsedResume

@pytest.fixture
def checker():
    return EligibilityChecker()

def test_eligible_candidate(checker):
    """Candidate with both Python and LangGraph/RAG is eligible."""
    parsed = ParsedResume(
        file_path="synthetic_1.pdf",
        file_name="synthetic_1.pdf",
        raw_text="Experienced in Python, FastAPI, and building LangGraph agentic workflows with RAG and Pinecone.",
        candidate_name="Alice Developer",
        skills=["Python", "FastAPI", "LangGraph", "RAG", "Pinecone"],
    )
    is_eligible, reasons, py_ev, ai_ev = checker.check_eligibility(parsed)
    assert is_eligible is True
    assert len(reasons) == 0
    assert "Python" in py_ev
    assert len(ai_ev) > 0

def test_python_only_rejected(checker):
    """Candidate with strong Python but no AI/agentic exposure is rejected."""
    parsed = ParsedResume(
        file_path="synthetic_2.pdf",
        file_name="synthetic_2.pdf",
        raw_text="Experienced in Python backend engineering, Django, PostgreSQL, Celery, and Redis caching.",
        candidate_name="Bob Backend",
        skills=["Python", "Django", "PostgreSQL", "Redis", "Celery"],
    )
    is_eligible, reasons, py_ev, ai_ev = checker.check_eligibility(parsed)
    assert is_eligible is False
    assert "No AI/agentic project evidence" in reasons
    assert "No evidence of Python stack" not in reasons

def test_ai_only_no_python_rejected(checker):
    """Candidate with JS/Node LangChain but zero Python is rejected."""
    parsed = ParsedResume(
        file_path="synthetic_3.pdf",
        file_name="synthetic_3.pdf",
        raw_text="Full-stack JavaScript engineer building AI agents with LangChain.js, Node.js, and React.",
        candidate_name="Charlie JS",
        skills=["JavaScript", "Node.js", "React", "LangChain"],
    )
    is_eligible, reasons, py_ev, ai_ev = checker.check_eligibility(parsed)
    assert is_eligible is False
    assert "No evidence of Python stack" in reasons

def test_java_mern_only_rejected(checker):
    """Java / React / Spring Boot profile without Python or AI is rejected with both reasons."""
    parsed = ParsedResume(
        file_path="synthetic_4.pdf",
        file_name="synthetic_4.pdf",
        raw_text="Java developer with 2 years building Spring Boot microservices, MySQL databases, and React UI.",
        candidate_name="David Enterprise",
        skills=["Java", "Spring Boot", "MySQL", "React"],
    )
    is_eligible, reasons, py_ev, ai_ev = checker.check_eligibility(parsed)
    assert is_eligible is False
    assert "No evidence of Python stack" in reasons
    assert "No AI/agentic project evidence" in reasons

def test_python_ai_with_react_allowed(checker):
    """Presence of React/Next.js/Java does NOT cause rejection if Python + AI are satisfied."""
    parsed = ParsedResume(
        file_path="synthetic_5.pdf",
        file_name="synthetic_5.pdf",
        raw_text="Full stack engineer skilled in Python, FastAPI, React, Next.js, and LlamaIndex RAG pipelines.",
        candidate_name="Eve Fullstack",
        skills=["Python", "FastAPI", "React", "Next.js", "LlamaIndex", "RAG"],
    )
    is_eligible, reasons, py_ev, ai_ev = checker.check_eligibility(parsed)
    assert is_eligible is True
    assert len(reasons) == 0
