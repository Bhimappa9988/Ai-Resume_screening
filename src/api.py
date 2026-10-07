import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel

from src.models import ScreeningResponse, BatchSummary
from src.pipeline import ResumeScreeningPipeline
from src.config import config

app = FastAPI(
    title="AI Resume Screening & Ranking API",
    description="Production-minded screening and ranking API for SDE Interns (Python + AI)",
    version="1.0.0",
)

# Global in-memory cache for latest screening response
_cached_response: Optional[ScreeningResponse] = None

class ScreenRequest(BaseModel):
    input_dir: Optional[str] = "./resumes"
    output_path: Optional[str] = "./output/results.json"
    enable_github: Optional[bool] = True
    max_workers: Optional[int] = 6

@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "healthy",
        "service": "AI Resume Screening & Ranking API",
        "version": "1.0.0",
    }

@app.post("/screen", response_model=ScreeningResponse, tags=["Screening"])
def run_screening(req: ScreenRequest):
    """
    Triggers resume screening pipeline over the specified input folder.
    Returns ranked shortlist and batch summary.
    """
    global _cached_response

    input_path = Path(req.input_dir or "./resumes")
    if not input_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Input directory not found: {req.input_dir}",
        )

    pipeline = ResumeScreeningPipeline(
        enable_github=req.enable_github if req.enable_github is not None else True,
        max_workers=req.max_workers or 6,
    )

    try:
        response = pipeline.run_screening(str(input_path))
        _cached_response = response

        # Save to disk
        out_file = req.output_path or "./output/results.json"
        pipeline.export_results(response, out_file)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screening error: {str(e)}")

@app.get("/results", tags=["Screening"])
def get_results():
    """
    Retrieve the most recent screening results.
    """
    global _cached_response
    if _cached_response:
        return _cached_response

    # Try reading from disk
    default_json = Path("./output/results_detailed.json")
    if default_json.exists():
        try:
            with open(default_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception:
            pass

    flat_json = Path("./output/results.json")
    if flat_json.exists():
        try:
            with open(flat_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {"candidates": data}
        except Exception:
            pass

    raise HTTPException(
        status_code=404,
        detail="No screening results found. Please call POST /screen first.",
    )
