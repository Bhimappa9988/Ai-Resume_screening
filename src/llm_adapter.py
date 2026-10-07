import os
import re
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import httpx

from src.config import config
from src.models import ParsedResume

class ProjectQualityAssessment(BaseModel):
    is_thin_wrapper: bool = Field(False, description="True if AI project is merely a simple API wrapper or tutorial clone")
    penalty_points: int = Field(0, ge=0, le=15, description="Penalty points (5-15) if thin wrapper or tutorial project")
    penalty_reason: str = Field("", description="Justification for penalty if applicable")
    project_summary: str = Field("", description="Evidence-backed summary of real projects")
    key_strengths: List[str] = Field(default_factory=list, description="Key candidate engineering strengths")
    key_concerns: List[str] = Field(default_factory=list, description="Key flags or missing signals")

class LLMAdapter:
    """
    Adapter for AI/LLM semantic evaluation of candidate project quality.
    Supports OpenAI, Groq, and Gemini endpoints.
    Provides graceful deterministic fallback if no API key is configured or on failure.
    """

    def __init__(self):
        self.openai_key = config.openai_api_key
        self.groq_key = config.groq_api_key
        self.gemini_key = config.gemini_api_key

    def is_available(self) -> bool:
        return bool(self.openai_key or self.groq_key or self.gemini_key)

    def evaluate_candidate(self, parsed: ParsedResume) -> ProjectQualityAssessment:
        """
        Evaluate project quality, detect thin wrappers/tutorials, and summarize achievements.
        Falls back to rule-based heuristics if no LLM key is configured or if API call fails.
        """
        if self.groq_key:
            try:
                return self._call_openai_compatible(
                    parsed,
                    api_key=self.groq_key,
                    base_url="https://api.groq.com/openai/v1/chat/completions",
                    model="llama-3.3-70b-versatile"
                )
            except Exception:
                pass

        if self.openai_key:
            try:
                return self._call_openai_compatible(
                    parsed,
                    api_key=self.openai_key,
                    base_url="https://api.openai.com/v1/chat/completions",
                    model="gpt-4o-mini"
                )
            except Exception:
                pass

        # Fallback to intelligent deterministic heuristic engine
        return self._heuristic_evaluation(parsed)

    def _call_openai_compatible(self, parsed: ParsedResume, api_key: str, base_url: str, model: str) -> ProjectQualityAssessment:
        prompt = f"""
You are an expert AI engineering recruiter assessing a candidate's resume for an SDE Intern (Python + AI) role.
Evaluate the following candidate projects and experience:

Candidate: {parsed.candidate_name}
Extracted Skills: {', '.join(parsed.skills)}
Projects and Experience:
{parsed.sections.get('projects', '')}
{parsed.sections.get('experience', '')}

Evaluate:
1. Is the AI project merely a thin wrapper around an LLM API call (e.g., just calling openai.ChatCompletion without RAG, orchestration, evaluation, state, or tools)? Or a generic tutorial clone?
2. If thin wrapper / tutorial, deduct 5 to 15 penalty points.
3. Provide an evidence-backed project summary (1-2 sentences).
4. List 2-3 specific technical strengths.
5. List 1-2 concerns/gaps.

Respond strictly in valid JSON matching:
{{
    "is_thin_wrapper": false,
    "penalty_points": 0,
    "penalty_reason": "",
    "project_summary": "...",
    "key_strengths": ["...", "..."],
    "key_concerns": ["..."]
}}
"""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a precise technical hiring evaluator. Return only JSON."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 500
        }

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(base_url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                parsed_json = json.loads(content)
                return ProjectQualityAssessment(**parsed_json)
            else:
                raise RuntimeError(f"LLM API returned status {resp.status_code}")

    def _heuristic_evaluation(self, parsed: ParsedResume) -> ProjectQualityAssessment:
        """
        Deterministic heuristic evaluator providing reliable, explainable signals
        when running offline or without an active LLM API key.
        """
        text = parsed.raw_text.lower()
        projects_text = parsed.sections.get("projects", "").lower()
        exp_text = parsed.sections.get("experience", "").lower()
        combined_proj = projects_text + "\n" + exp_text

        is_thin_wrapper = False
        penalty_points = 0
        penalty_reasons = []

        # Thin wrapper detection:
        # Candidate claims "AI/LLM chatbot" but only mentions basic prompt/api call with no vector DB, no tools, no agents, no RAG
        has_basic_api = bool(re.search(r"\bopenai api\b|\bchatgpt api\b|\bgpt api\b|\bgpt-3\.5\b", text))
        has_deep_ai = any(kw in text for kw in [
            "langgraph", "llamaindex", "autogen", "crewai", "rag", "vector", "chroma",
            "pinecone", "faiss", "qdrant", "weaviate", "tool calling", "multi-agent", "rerank", "embeddings"
        ])
        
        # Check for tutorial project titles
        tutorial_patterns = [
            r"\bchatgpt clone\b",
            r"\bsimple chatbot\b",
            r"\btwitter clone\b",
            r"\btodo app\b",
            r"\bnetflix clone\b",
        ]
        is_tutorial = any(re.search(pat, text) for pat in tutorial_patterns)

        if has_basic_api and not has_deep_ai:
            is_thin_wrapper = True
            penalty_points += 10
            penalty_reasons.append("Project appears to be a thin wrapper around LLM API without retrieval, state, or tools.")

        if is_tutorial:
            penalty_points += 5
            penalty_reasons.append("Generic tutorial-style project listed with minimal evidence of custom system design.")

        penalty_points = min(15, penalty_points)
        penalty_reason = "; ".join(penalty_reasons)

        # Strengths detection
        strengths = []
        if any(kw in text for kw in ["langgraph", "multi-agent", "agentic", "crewai"]):
            strengths.append("Stateful / multi-agent workflow architecture")
        elif any(kw in text for kw in ["rag", "vector", "pinecone", "chroma", "faiss"]):
            strengths.append("Retrieval-Augmented Generation (RAG) pipeline with vector search")
        elif any(kw in text for kw in ["tool calling", "function calling"]):
            strengths.append("Agentic tool and function calling integration")

        if any(kw in text for kw in ["fastapi", "asyncio"]):
            strengths.append("Modern asynchronous Python backend (FastAPI/asyncio)")
        elif "django" in text or "flask" in text:
            strengths.append("Python web backend development experience")

        if "docker" in text or "kubernetes" in text:
            strengths.append("Containerized deployment exposure (Docker/K8s)")
        if "postgresql" in text or "redis" in text:
            strengths.append("Relational database & caching integration (PostgreSQL/Redis)")

        if not strengths:
            strengths.append("Basic Python software development foundation")

        # Concerns detection
        concerns = []
        if "redis" not in text:
            concerns.append("Limited Redis / caching evidence")
        if not any(kw in text for kw in ["pytest", "unit test", "tdd", "ci/cd"]):
            concerns.append("Limited automated testing (pytest/CI) evidence")
        if not any(kw in text for kw in ["docker", "gcp", "aws"]):
            concerns.append("Limited cloud / container deployment evidence")
        if penalty_points > 0:
            concerns.append(f"Penalty applied: {penalty_reason}")

        # Evidence-backed project summary
        summary_sentences = []
        if "langgraph" in text:
            summary_sentences.append("Built stateful agentic workflows using LangGraph.")
        elif "rag" in text:
            summary_sentences.append("Implemented RAG pipelines with semantic vector retrieval and document chunking.")
        elif any(kw in text for kw in ["langchain", "llamaindex"]):
            summary_sentences.append("Developed LLM applications with LangChain / LlamaIndex framework integration.")
        elif any(kw in text for kw in ["openai", "gemini", "claude"]):
            summary_sentences.append("Integrated LLM API completions and prompt engineering.")
        else:
            summary_sentences.append("Built Python-based applications and software services.")

        if "fastapi" in text or "django" in text or "flask" in text:
            backend_kw = "FastAPI" if "fastapi" in text else ("Django" if "django" in text else "Flask")
            summary_sentences.append(f"Engineered backend REST APIs with {backend_kw}.")

        project_summary = " ".join(summary_sentences)

        return ProjectQualityAssessment(
            is_thin_wrapper=is_thin_wrapper,
            penalty_points=penalty_points,
            penalty_reason=penalty_reason,
            project_summary=project_summary,
            key_strengths=strengths[:3],
            key_concerns=concerns[:2],
        )
