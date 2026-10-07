import pytest
from src.parser import ResumeParser

@pytest.fixture
def parser():
    return ResumeParser()

def test_extract_email(parser):
    text = "Please reach out to dev.engineer_99@test-corp.org for any inquiries."
    email = parser.extract_email(text)
    assert email == "dev.engineer_99@test-corp.org"

def test_extract_phone(parser):
    text = "Call me at +91 9876543210 or alternate +91-7488615976"
    phone = parser.extract_phone(text)
    assert phone is not None
    assert "9876543210" in phone

def test_extract_skills_boundary(parser):
    """Ensure token boundaries work so substrings like 'Go' in 'Google' don't trigger false positives."""
    text = "I use Google Cloud, React, and Python. We build RAG pipelines."
    skills = parser.extract_skills(text)
    assert "Python" in skills
    assert "React" in skills
    assert "RAG" in skills

def test_candidate_name_fallback_from_email(parser):
    text = "RESUME\nSUMMARY\nSoftware Engineer with passion."
    name = parser.extract_candidate_name(text, "candidate_01.pdf", "suresh.raina@domain.com")
    assert name == "Suresh Raina"

def test_github_link_extraction(parser):
    text = "Profile: https://github.com/developer-hero/portfolio"
    url, username = parser.extract_github(text, [])
    assert username == "developer-hero"
    assert url == "https://github.com/developer-hero"
