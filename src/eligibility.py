import re
from typing import List, Tuple, Dict, Any
from src.models import ParsedResume

# Regex patterns for Python stack verification
PYTHON_PATTERNS = [
    r"\bpython(?:3)?\b",
    r"\bfastapi\b",
    r"\bflask\b",
    r"\bdjango\b",
    r"\basyncio\b",
    r"\bsqlalchemy\b",
    r"\bpytest\b",
    r"\bcelery\b",
    r"\bpytorch\b",
]

# Patterns representing AI / LLM / RAG / Agentic requirements
AI_AGENTIC_PATTERNS = [
    # Agentic frameworks & architectures
    r"\blanggraph\b",
    r"\blangchain\b",
    r"\bllamaindex\b|\bllama-index\b",
    r"\bcrewai\b|\bcrew-ai\b",
    r"\bautogen\b",
    r"\bgoogle adk\b|\badk\b",
    r"\bagentic\b|\bmulti[- ]agent\b|\bai agents?\b|\bautonomous agents?\b",
    r"\btool[- ]calling\b|\bfunction[- ]calling\b",
    r"\breact agent\b|\bstateful graph\b|\bstategraph\b",

    # RAG & Semantic Retrieval
    r"\brag\b|\bretrieval[- ]augmented\b",
    r"\bvector (?:db|database|search|store)\b|\bvectorstore\b",
    r"\bchroma\b|\bchromadb\b",
    r"\bpinecone\b",
    r"\bfaiss\b",
    r"\bweaviate\b",
    r"\bqdrant\b",
    r"\bembeddings?\b",
    r"\bsemantic search\b|\bhybrid search\b|\brerank(?:ing)?\b",

    # LLM systems & APIs
    r"\bllms?\b|\blarge language models?\b",
    r"\bopenai\b|\bgpt[- ]?[34o]\b",
    r"\bgemini\b",
    r"\bclaude\b|\banthropic\b",
    r"\bhugging\s*face\b|\btransformers\b",
    r"\bollama\b|\bvllm\b",
    r"\bnvidia nim\b",
    r"\bdeepseek\b",
    r"\bragas\b|\blangsmith\b|\bprompt engineering\b",
]

class EligibilityChecker:
    """
    Hard rule-based eligibility filter according to Section 3 of the assignment.
    A candidate is eligible ONLY when both conditions are satisfied:
      1. Genuine Python evidence
      2. Meaningful AI/LLM/RAG/agentic project or framework evidence
    """

    def evaluate_python_evidence(self, text: str, skills: List[str]) -> Tuple[bool, List[str]]:
        evidence = []
        text_lower = text.lower()

        # Check explicit skill list
        python_skills = {"Python", "FastAPI", "Flask", "Django", "Asyncio", "Pytest", "SQLAlchemy"}
        for s in skills:
            if s in python_skills and s not in evidence:
                evidence.append(s)

        # Check raw text for patterns
        for pattern in PYTHON_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                term = match.group(0).capitalize()
                if term not in evidence:
                    evidence.append(term)

        is_present = len(evidence) > 0
        return is_present, evidence

    def evaluate_ai_evidence(self, text: str, skills: List[str]) -> Tuple[bool, List[str]]:
        evidence = []
        text_lower = text.lower()

        ai_skills = {
            "LangGraph", "LangChain", "LlamaIndex", "CrewAI", "AutoGen",
            "Google ADK", "RAG", "Vector Search", "ChromaDB", "Pinecone",
            "FAISS", "Weaviate", "Qdrant", "Embeddings", "Tool Calling",
            "Multi-Agent Systems", "LLM", "OpenAI", "Google Gemini",
            "Anthropic Claude", "Hugging Face", "Ollama", "vLLM", "Nvidia NIM"
        }
        for s in skills:
            if s in ai_skills and s not in evidence:
                evidence.append(s)

        for pattern in AI_AGENTIC_PATTERNS:
            matches = re.findall(pattern, text_lower)
            for m in matches:
                clean_m = m.strip()
                if clean_m and clean_m.upper() not in [e.upper() for e in evidence]:
                    evidence.append(clean_m)

        is_present = len(evidence) > 0
        return is_present, evidence

    def check_eligibility(self, parsed: ParsedResume) -> Tuple[bool, List[str], List[str], List[str]]:
        """
        Returns:
            is_eligible: bool
            rejection_reasons: List[str]
            python_evidence: List[str]
            ai_evidence: List[str]
        """
        rejection_reasons = []

        has_python, py_evidence = self.evaluate_python_evidence(parsed.raw_text, parsed.skills)
        if not has_python:
            rejection_reasons.append("No evidence of Python stack")

        has_ai, ai_evidence = self.evaluate_ai_evidence(parsed.raw_text, parsed.skills)
        if not has_ai:
            rejection_reasons.append("No AI/agentic project evidence")

        is_eligible = (has_python and has_ai)
        return is_eligible, rejection_reasons, py_evidence, ai_evidence
