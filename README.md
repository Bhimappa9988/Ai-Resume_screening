# AI Resume Screening & Ranking System

A production-minded, explainable screening and ranking engine built in Python for hiring **SDE Interns with a strong Python foundation and practical AI/agentic systems exposure**.

The system ingests a batch of resumes (PDF/DOCX/TXT), enforces strict rule-based eligibility filtering, enriches candidate profiles via the public GitHub API and structured LLM evaluation, scores candidates across a 100-point rubric with penalties for shallow projects, and outputs an explainable, ranked shortlist.

---

## Architecture Overview

```mermaid
flowchart TD
    A[Input Resumes Folder\nPDF / DOCX / TXT] --> B[Resilient Parser\nText, Links, Annotations, Skills]
    B --> C{Hard Eligibility Filter\nPython + AI Rules}
    C -- Failed --> D[Rejected Candidates\nExplicit Disqualification Reasons]
    C -- Passed --> E[Candidate Profile Enrichment]
    E --> F[Public GitHub API\nRecent Events, Commits, Repos]
    E --> G[LLM / Heuristic Semantic Evaluator\nThin-Wrapper & Tutorial Detection]
    F --> H[100-Point Scoring Model\nAI Depth: 40 | Python: 30 | Cloud: 15 | GH: 10 | Eng: 5]
    G --> H
    H --> I[Ranking Engine\nSort by Score & Tie-Breakers]
    I --> J[Outputs\nresults.json + report.html + Batch Summary]
    D --> J
```

---

## Key Features

1. **Robust Multi-Format Parsing**:
   - Ingests **PDF**, **DOCX**, and **TXT** files.
   - Extracts clickable hyperlinks from PDF annotations (`/Annots -> /URI`), capturing GitHub and LinkedIn URLs hidden behind text labels.
   - Fault-tolerant: Corrupted or unreadable files are recorded in the batch summary without crashing the run.
2. **Hard Rule-Based Filtering**:
   - **Condition 1 (Python Evidence)**: Must show genuine Python presence (Python, FastAPI, Flask, Django, etc.). React/Java-only profiles are disqualified.
   - **Condition 2 (AI/Agentic Evidence)**: Must demonstrate meaningful AI/LLM/RAG/agentic exposure (LangGraph, LangChain, LlamaIndex, vector DBs, tool calling, embeddings). Pure classical ML (e.g., standalone Scikit-learn without LLM/agent components) is disqualified.
   - Disqualified candidates are logged with explicit rejection reasons (e.g., `"No evidence of Python stack"`, `"No AI/agentic project evidence"`).
3. **100-Point Explainable Scoring Model**:
   - **AI / Agentic / RAG Project Depth (40 pts)**: Rewards stateful multi-agent systems, LangGraph, RAG pipelines, vector retrieval, and tool calling.
   - **Python & Backend Engineering (30 pts)**: Rewards modern async frameworks (FastAPI), asyncio, relational databases (PostgreSQL), and caching/queues (Redis, Celery).
   - **Cloud / Deployment / Full Stack (15 pts)**: Docker, Kubernetes, GCP/AWS, and supporting React/Next.js integrations.
   - **GitHub Activity (10 pts)**: Public activity frequency (0–5 pts) + maintained relevant Python/AI repositories (0–5 pts).
   - **Engineering Depth Signals (5 pts)**: Automated testing (pytest), CI/CD, rate limiting, and observability.
   - **Project-Quality Penalties (-5 to -15 pts)**: Deducts points for thin OpenAI wrappers, simple prompt bots, or generic tutorial clones lacking custom logic.
4. **GitHub Public API Enrichment**:
   - Queries `https://api.github.com` for recent events, commit activity, and repository languages.
   - In-memory cache eliminates redundant network requests.
   - Resilient against GitHub rate limits (HTTP 403/429) or private profiles: records status gracefully without penalizing or halting the batch.
5. **Hybrid AI/LLM Adapter**:
   - Pluggable adapter supporting OpenAI (`gpt-4o-mini`), Groq (`llama-3.3-70b-versatile`), and Gemini via environment variables.
   - Returns structured Pydantic models.
   - Includes a deterministic heuristic engine that operates completely offline when no API key is provided.
6. **Dual Interfaces**:
   - **CLI**: `python main.py --input ./resumes --output ./output/results.json`
   - **FastAPI**: `POST /screen`, `GET /results`, `GET /health` with interactive Swagger UI (`/docs`).

---

## Directory Structure

```
resume_dataset_50/
├── resumes/                 # 50 Candidate PDF resumes
├── src/
│   ├── __init__.py
│   ├── config.py            # Centralized settings & weights
│   ├── models.py            # Pydantic schemas for data integrity
│   ├── parser.py            # PDF/DOCX/TXT parser & link extractor
│   ├── eligibility.py       # Hard rule-based filtering
│   ├── github_enricher.py   # Public GitHub API client & cache
│   ├── llm_adapter.py       # LLM provider adapter & heuristic engine
│   ├── scoring.py           # 100-point rubric & penalty deductions
│   ├── pipeline.py          # Batch orchestrator & exporter
│   └── api.py               # FastAPI application
├── tests/
│   ├── test_eligibility.py  # Hard filter tests
│   ├── test_scoring.py      # Rubric, capping & penalty tests
│   ├── test_parser.py       # Name, link & regex tests
│   ├── test_pipeline.py     # Fault-tolerance & synthetic batch tests
│   └── test_api.py          # FastAPI endpoint tests
├── output/
│   ├── results.json         # Primary JSON output for the 50 resumes
│   ├── results_detailed.json# JSON with embedded batch metadata
│   └── report.html          # Interactive visual HTML report
├── main.py                  # CLI entrypoint
├── requirements.txt         # Pinned dependencies
├── .env.example             # Environment variable template
└── README.md                # System documentation & rationale
```

---

## Installation & Setup

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.13)
- pip

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Optional Environment Variables
Copy `.env.example` to `.env` if you wish to configure API keys:
```bash
# Optional: Higher GitHub rate limits (5,000 req/hr vs 60 req/hr)
GITHUB_TOKEN=your_github_token

# Optional: LLM keys for semantic analysis (the system falls back to heuristics if omitted)
GROQ_API_KEY=your_groq_key
OPENAI_API_KEY=your_openai_key
```

---

## How to Run

### Option 1: Command Line Interface (CLI)

Run screening over the default `./resumes` folder:
```bash
python main.py --input ./resumes --output ./output/results.json
```

Custom arguments:
```bash
python main.py \
  --input ./resumes \
  --output ./output/results.json \
  --html ./output/report.html \
  --workers 6
```

To run completely offline without querying GitHub:
```bash
python main.py --input ./resumes --no-github
```

### Option 2: FastAPI Web Service

Start the FastAPI server:
```bash
uvicorn src.api:app --host 127.0.0.1 --port 8000 --reload
```

- **Interactive Swagger Docs**: Open `http://127.0.0.1:8000/docs` in your browser.
- **Trigger Screening**:
  ```bash
  curl -X POST "http://127.0.0.1:8000/screen" -H "Content-Type: application/json" -d "{\"input_dir\": \"./resumes\"}"
  ```
- **Fetch Latest Results**:
  ```bash
  curl -X GET "http://127.0.0.1:8000/results"
  ```
- **Health Check**:
  ```bash
  curl -X GET "http://127.0.0.1:8000/health"
  ```

---

## Running the Automated Test Suite

Run all 17 unit and integration tests using pytest:
```bash
pytest -v
```

---

## Batch Screening Results (50 Resumes)

When evaluated against the 50 resumes in `resumes/`:

| Metric | Result |
| :--- | :--- |
| **Total Resumes Ingested** | **50** |
| **Successfully Parsed** | **50** (100% parse success) |
| **Eligible Candidates** | **36** |
| **Hard Filter Disqualified** | **14** |
| **Malformed / Unreadable** | **0** |

### Top Ranked Eligible Candidates:
1. **Yash Maini** (Total: **88/100**) — LangGraph, LangChain, RAG, Fine-Tuning, vLLM, FastAPI, Redis, Docker, active GitHub.
2. **Gourab Das** (Total: **81/100**) — Python, FastAPI, Asyncio, PostgreSQL, Docker, LangChain, RAG, active GitHub.
3. **Prathamesh** (Total: **79/100**) — LangGraph, multi-agent workflows, FastAPI, PostgreSQL, Redis, Docker.
4. **Shaiksultanasumaiya** (Total: **76/100**) — LangChain, LangGraph, RAG, Pinecone, FastAPI, Docker, active GitHub.
5. **V Sree Raghu Vardhan** (Total: **76/100**) — RAG pipelines, ChromaDB, FastAPI, PostgreSQL, Docker.
6. **Priyanshu Kumar** (Total: **75/100**) — LangGraph, RAG, tool calling, FastAPI, PostgreSQL, Docker.
7. **Abhinav** (Total: **74/100**) — LangGraph, RAG, vector search, active GitHub.

---

## Design Decisions

### 1. Hard Filtering Strategy
- **Rule-Based Isolation**: Hard filtering is deliberately executed **strictly outside the LLM**. LLMs can hallucinate qualifications or inflate scores for well-formatted resumes that lack core prerequisites.
- **Two Invariant Gates**:
  1. *Python Stack*: The candidate must demonstrate Python or core Python framework experience (FastAPI, Flask, Django, etc.). Candidates whose background is solely Java/Spring Boot or JavaScript/React/MERN are immediately disqualified.
  2. *AI / Agentic Exposure*: Must show concrete evidence of LLM, RAG, embeddings, vector databases, or agentic systems. Candidates with only classical tabular ML (e.g., standard Scikit-learn regression without LLM/agentic exposure) are disqualified.
- **Fair Inclusivity**: Presence of supporting technologies like React, Next.js, or Java does *not* disqualify a candidate, as long as both Python and AI requirements are met.

### 2. 100-Point Scoring Model & Penalties
- **Project Evidence Over Keywords**: The scorer searches for technologies within the candidate's actual `projects` and `experience` sections rather than merely matching keyword lists in the skills section.
- **Granular Weight Distribution**:
  - *AI / Agentic Depth (40 pts)*: Tiered by architectural sophistication (Multi-agent/LangGraph > RAG/Vector DB > Tool Calling > LLM API integration).
  - *Python Backend (30 pts)*: Rewards FastAPI and async programming higher than legacy sync frameworks, with extra points for PostgreSQL and Redis caching.
  - *Cloud / Deployment (15 pts)*: Rewards Docker/Kubernetes containerization and GCP/AWS deployment.
  - *GitHub Activity (10 pts)*: Rewards verifiable public activity and maintained Python/AI repositories.
  - *Engineering Depth (5 pts)*: Rewards automated testing (`pytest`), CI/CD, rate limiting, and observability.
- **Penalties for Thin Wrappers**: An automated deduction of 5 to 15 points is applied when an AI project is identified as a trivial wrapper around an API call (e.g., a simple chatbot prompt without retrieval, state, or tools) or a generic tutorial clone.

### 3. LLM Usage & Robust Fallback
- **Structured JSON Schema**: Prompts enforce a strict Pydantic model (`ProjectQualityAssessment`) to obtain deterministic JSON containing summary, strengths, concerns, and wrapper flags.
- **Provider Abstraction**: A unified adapter interfaces with OpenAI, Groq, or Gemini via standard environment variables.
- **Deterministic Heuristic Fallback**: If no API key is supplied, network connectivity drops, or a model call fails, the system transitions to a regex-based heuristic engine. The screening process never crashes due to an external API outage.

### 4. GitHub Enrichment Strategy
- **Hyperlink Annotation Extraction**: Many candidates embed their GitHub profile URL inside PDF link annotations rather than plain text. Extracting PDF annotations (`/Annots -> /URI`) increased GitHub profile discovery by >80%.
- **Rate-Limit Resilience**: The public unauthenticated GitHub API limits requests to 60 calls/hour. The enricher captures HTTP 403/429 responses, logs the status, and assigns 0 GitHub points without failing the batch or penalizing other criteria.
- **In-Memory Caching**: Cache keys by username ensure duplicate profile references generate zero redundant network calls.

---

## If I Had More Time

If allotted additional time, the following improvements would be prioritized:

1. **Async Batch Concurrent GitHub & LLM Processing with Token-Bucket Rate Limiter**:
   - Replace the current threadpool with an `asyncio` event loop using `httpx.AsyncClient` and a token-bucket rate limiter. This would enable screening 500+ resumes within seconds while strictly honoring third-party API quotas.
2. **Embedding-Based Semantic Match & Hallucination Cross-Verification**:
   - Compute embedding similarity between candidate project descriptions and the target SDE Intern job specification using a local lightweight embedding model (e.g., `all-MiniLM-L6-v2`), complementing keyword regex with dense semantic retrieval.
3. **Deep GitHub Repository Code Analysis**:
   - Instead of checking only repository metadata, fetch and inspect ASTs or commit diffs of candidate repositories to verify code quality, test coverage, and confirm genuine contribution ownership (vs. forked repositories).
4. **Interactive Human-in-the-Loop Web Review UI**:
   - Provide a lightweight React/Tailwind frontend allowing recruiters to review candidate rankings, adjust category weights dynamically, inspect highlighted PDF snippets side-by-side with score breakdowns, and export customized shortlist packages.
