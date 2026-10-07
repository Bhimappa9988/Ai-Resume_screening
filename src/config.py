import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class ScreeningConfig:
    # Directories & Paths
    default_input_dir: str = "./resumes"
    default_output_path: str = "./output/results.json"
    default_html_report_path: str = "./output/report.html"

    # API Keys & External Services
    github_token: Optional[str] = os.getenv("GITHUB_TOKEN")
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY")
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")

    # GitHub Enrichment Configuration
    github_api_base: str = "https://api.github.com"
    github_timeout_sec: float = 6.0
    github_max_score: int = 10
    enable_github_enrichment: bool = True

    # Scoring Weights (Total = 100)
    weight_ai_project_depth: int = 40
    weight_python_backend: int = 30
    weight_cloud_fullstack: int = 15
    weight_github_activity: int = 10
    weight_engineering_depth: int = 5

    # Penalties
    thin_wrapper_penalty: int = 10
    tutorial_penalty: int = 5

    # Concurrency
    max_workers: int = 6

config = ScreeningConfig()
