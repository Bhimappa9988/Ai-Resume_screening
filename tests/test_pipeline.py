import pytest
from pathlib import Path
from src.pipeline import ResumeScreeningPipeline

def test_pipeline_on_malformed_file(tmp_path):
    """Ensure unreadable or corrupt file does not crash pipeline and is counted as unreadable."""
    corrupt_file = tmp_path / "corrupt.pdf"
    corrupt_file.write_bytes(b"%PDF-1.5 THIS IS NOT A VALID PDF FILE")

    pipeline = ResumeScreeningPipeline(enable_github=False)
    response = pipeline.run_screening(str(tmp_path))

    assert response.batch_summary.total_resumes == 1
    assert response.batch_summary.failed_unreadable == 1
    assert len(response.ranked_candidates) == 0

def test_pipeline_synthetic_batch(tmp_path):
    """Test full batch pipeline with a synthetic text file."""
    synth_file = tmp_path / "candidate_test.txt"
    synth_file.write_text(
        "Kiran Kumar\nEmail: kiran.kumar@test.com\nSkills: Python, FastAPI, LangGraph, RAG, Docker\n"
        "Projects: Built an intelligent agentic workflow using LangGraph and RAG retrieval.\n",
        encoding="utf-8"
    )

    pipeline = ResumeScreeningPipeline(enable_github=False)
    response = pipeline.run_screening(str(tmp_path))

    assert response.batch_summary.total_resumes == 1
    assert response.batch_summary.successfully_parsed == 1
    assert response.batch_summary.eligible == 1
    assert len(response.ranked_candidates) == 1
    assert response.ranked_candidates[0].rank == 1
    assert response.ranked_candidates[0].eligible is True
