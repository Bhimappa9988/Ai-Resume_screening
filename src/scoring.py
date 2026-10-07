import re
from typing import Dict, Any, List, Tuple
from src.models import ParsedResume, ScoreBreakdown
from src.llm_adapter import ProjectQualityAssessment
from src.config import config

class CandidateScorer:
    """
    100-Point Scoring Engine according to Section 4 of the assignment:
      - AI / Agentic / RAG Project Depth: 40 points
      - Python & Backend Engineering: 30 points
      - Cloud / Deployment / Full Stack: 15 points
      - GitHub Activity: 10 points
      - Engineering Depth Signals: 5 points
      - Penalties: -5 to -15 points for thin wrappers or tutorial-only projects
    """

    def score_candidate(
        self,
        parsed: ParsedResume,
        github_enrichment: Dict[str, Any],
        quality_assessment: ProjectQualityAssessment,
    ) -> Tuple[int, ScoreBreakdown, List[str], List[str]]:
        """
        Compute total score and breakdown.
        Returns:
            total_score: int (0-100)
            breakdown: ScoreBreakdown
            strengths: List[str]
            concerns: List[str]
        """
        raw_text = parsed.raw_text.lower()
        projects_text = (parsed.sections.get("projects", "") + "\n" + parsed.sections.get("experience", "")).lower()
        if not projects_text.strip():
            projects_text = raw_text

        # 1. AI / Agentic / RAG Project Depth (Max 40)
        ai_score = 0
        
        # Stateful multi-agent / orchestration (LangGraph, CrewAI, AutoGen, multi-agent)
        if any(kw in projects_text for kw in ["langgraph", "crewai", "autogen", "multi-agent", "agentic workflow", "stategraph"]):
            ai_score += 15
        elif any(kw in raw_text for kw in ["langgraph", "crewai", "autogen", "multi-agent"]):
            ai_score += 7

        # RAG & Semantic Retrieval (RAG, vector db, embeddings, semantic search)
        rag_kws = ["rag", "retrieval-augmented", "vector", "chroma", "pinecone", "faiss", "weaviate", "qdrant", "embeddings"]
        if any(kw in projects_text for kw in rag_kws):
            ai_score += 12
        elif any(kw in raw_text for kw in rag_kws):
            ai_score += 6

        # Tool calling / function calling
        if any(kw in projects_text for kw in ["tool-calling", "tool calling", "function calling", "function-calling"]):
            ai_score += 8
        elif any(kw in raw_text for kw in ["tool-calling", "tool calling", "function calling"]):
            ai_score += 3

        # Evaluation, guardrails, LangSmith, Ragas
        if any(kw in projects_text for kw in ["ragas", "trulens", "langsmith", "evaluation pipeline", "guardrails"]):
            ai_score += 5
        elif any(kw in raw_text for kw in ["ragas", "langsmith", "evaluation"]):
            ai_score += 2

        # Standard LLM frameworks / integrations (LangChain, LlamaIndex, OpenAI, Hugging Face)
        if any(kw in projects_text for kw in ["langchain", "llamaindex", "hugging face", "openai", "transformers"]):
            ai_score += 5

        ai_score = min(config.weight_ai_project_depth, ai_score)

        # 2. Python & Backend Engineering (Max 30)
        py_score = 0

        # Modern web framework: FastAPI vs Django/Flask
        if "fastapi" in projects_text:
            py_score += 10
        elif "fastapi" in raw_text:
            py_score += 6
        elif any(kw in projects_text for kw in ["django", "flask"]):
            py_score += 7
        elif any(kw in raw_text for kw in ["django", "flask"]):
            py_score += 4
        elif "python" in raw_text:
            py_score += 3

        # Async programming
        if any(kw in projects_text for kw in ["asyncio", "async/await", "asynchronous", "httpx", "aiohttp"]):
            py_score += 6
        elif any(kw in raw_text for kw in ["asyncio", "asynchronous"]):
            py_score += 3

        # Databases (PostgreSQL, SQLAlchemy, MongoDB, Redis)
        if any(kw in projects_text for kw in ["postgresql", "postgres", "sqlalchemy"]):
            py_score += 8
        elif any(kw in raw_text for kw in ["postgresql", "postgres", "sqlalchemy"]):
            py_score += 4
        elif any(kw in projects_text for kw in ["mysql", "mongodb", "sqlite"]):
            py_score += 4
        elif any(kw in raw_text for kw in ["mysql", "mongodb", "sqlite"]):
            py_score += 2

        # Caching & Queues (Redis, Celery, RabbitMQ, Kafka)
        if any(kw in projects_text for kw in ["redis", "celery", "rabbitmq", "kafka"]):
            py_score += 6
        elif any(kw in raw_text for kw in ["redis", "celery", "rabbitmq", "kafka"]):
            py_score += 3

        py_score = min(config.weight_python_backend, py_score)

        # 3. Cloud / Deployment / Full Stack (Max 15)
        cloud_score = 0

        # Docker / Kubernetes
        if any(kw in projects_text for kw in ["docker", "docker-compose", "kubernetes", "k8s"]):
            cloud_score += 6
        elif any(kw in raw_text for kw in ["docker", "kubernetes"]):
            cloud_score += 3

        # Cloud provider (GCP, AWS, Azure)
        if any(kw in projects_text for kw in ["gcp", "google cloud", "aws", "azure"]):
            cloud_score += 5
        elif any(kw in raw_text for kw in ["gcp", "google cloud", "aws", "azure"]):
            cloud_score += 2

        # Supporting UI / Full Stack (React, Next.js, Streamlit)
        if any(kw in projects_text for kw in ["react", "next.js", "streamlit", "typescript"]):
            cloud_score += 4
        elif any(kw in raw_text for kw in ["react", "next.js", "streamlit"]):
            cloud_score += 2

        cloud_score = min(config.weight_cloud_fullstack, cloud_score)

        # 4. GitHub Activity (Max 10)
        github_score = min(config.weight_github_activity, github_enrichment.get("score", 0))

        # 5. Engineering Depth Signals (Max 5)
        eng_score = 0

        # Testing & CI/CD
        if any(kw in raw_text for kw in ["pytest", "unit test", "tdd", "ci/cd", "github actions"]):
            eng_score += 3

        # Observability / Architecture / Rate limiting / Caching details
        if any(kw in raw_text for kw in ["rate limiting", "observability", "opentelemetry", "prometheus", "grafana", "concurrency", "caching"]):
            eng_score += 2

        eng_score = min(config.weight_engineering_depth, eng_score)

        # Deduct project quality penalties
        penalty = quality_assessment.penalty_points
        subtotal = ai_score + py_score + cloud_score + github_score + eng_score
        total_score = max(0, min(100, subtotal - penalty))

        breakdown = ScoreBreakdown(
            ai_project_depth=ai_score,
            python_backend=py_score,
            cloud_fullstack=cloud_score,
            github=github_score,
            engineering_depth=eng_score,
        )

        strengths = list(quality_assessment.key_strengths)
        concerns = list(quality_assessment.key_concerns)

        return total_score, breakdown, strengths, concerns
