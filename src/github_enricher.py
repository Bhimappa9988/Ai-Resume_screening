import os
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
import httpx

from src.config import config

class GitHubEnricher:
    """
    Enriches candidate data using public GitHub API.
    Provides activity score (0-5) and repo score (0-5) capped at 10 points.
    Gracefully handles rate limits, missing profiles, and timeouts.
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or config.github_token
        self.base_url = config.github_api_base
        self.timeout = config.github_timeout_sec
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AI-Resume-Screening-System/1.0",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def extract_username(self, github_input: Optional[str]) -> Optional[str]:
        if not github_input:
            return None
        clean = github_input.strip()
        m = re.search(r"(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9_-]+)/?", clean, re.I)
        if m:
            username = m.group(1)
        else:
            username = clean.lstrip("@").split("/")[0]

        if username.lower() in {"join", "login", "features", "explore", "pricing", "github"}:
            return None
        return username

    def enrich(self, github_input: Optional[str]) -> Dict[str, Any]:
        """
        Enrich a candidate from their GitHub profile or username.
        Returns a dict with:
            score: int (0-10)
            status: str
            summary: str
            details: dict
        """
        username = self.extract_username(github_input)
        if not username:
            return {
                "score": 0,
                "status": "missing",
                "summary": "No public GitHub profile provided.",
                "details": {},
            }

        if username in self._cache:
            return self._cache[username]

        result = self._fetch_github_data(username)
        self._cache[username] = result
        return result

    def _fetch_github_data(self, username: str) -> Dict[str, Any]:
        headers = self._get_headers()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                # 1. Fetch user profile
                user_resp = client.get(f"{self.base_url}/users/{username}", headers=headers)
                
                if user_resp.status_code == 404:
                    return {
                        "score": 0,
                        "status": "not_found",
                        "summary": f"GitHub profile '{username}' not found.",
                        "details": {},
                    }
                elif user_resp.status_code in (403, 429):
                    return {
                        "score": 0,
                        "status": "rate_limited",
                        "summary": "GitHub API rate limit reached; skipped enrichment without penalizing.",
                        "details": {},
                    }
                elif user_resp.status_code != 200:
                    return {
                        "score": 0,
                        "status": "api_error",
                        "summary": f"GitHub API error (status {user_resp.status_code}).",
                        "details": {},
                    }

                user_data = user_resp.json()
                public_repos = user_data.get("public_repos", 0)

                # 2. Fetch recent events (activity signal)
                events_resp = client.get(f"{self.base_url}/users/{username}/events?per_page=20", headers=headers)
                events_data = events_resp.json() if events_resp.status_code == 200 else []

                # 3. Fetch top repositories
                repos_resp = client.get(f"{self.base_url}/users/{username}/repos?sort=updated&per_page=10", headers=headers)
                repos_data = repos_resp.json() if repos_resp.status_code == 200 else []

                # Calculate Activity Score (0-5)
                recent_events_count = len(events_data) if isinstance(events_data, list) else 0
                activity_score = 0
                if recent_events_count >= 10:
                    activity_score = 5
                elif recent_events_count >= 5:
                    activity_score = 4
                elif recent_events_count >= 2:
                    activity_score = 3
                elif recent_events_count >= 1:
                    activity_score = 2
                elif public_repos > 0:
                    activity_score = 1

                # Calculate Repository Quality Score (0-5)
                repo_score = 0
                relevant_kw = {"python", "ai", "llm", "rag", "agent", "fastapi", "machine-learning", "pytorch"}
                matched_relevant = 0

                if isinstance(repos_data, list):
                    for r in repos_data:
                        lang = str(r.get("language") or "").lower()
                        desc = str(r.get("description") or "").lower()
                        name = str(r.get("name") or "").lower()
                        if lang == "python" or any(kw in desc or kw in name for kw in relevant_kw):
                            matched_relevant += 1

                if matched_relevant >= 3:
                    repo_score = 5
                elif matched_relevant >= 1:
                    repo_score = 4
                elif public_repos >= 5:
                    repo_score = 3
                elif public_repos >= 1:
                    repo_score = 2

                total_score = min(config.github_max_score, activity_score + repo_score)

                summary_parts = []
                if activity_score >= 3:
                    summary_parts.append(f"Actively committed ({recent_events_count} recent events)")
                elif activity_score >= 1:
                    summary_parts.append("Moderate recent activity")
                else:
                    summary_parts.append("Low recent activity")

                if matched_relevant > 0:
                    summary_parts.append(f"{matched_relevant} relevant Python/AI repositories")
                elif public_repos > 0:
                    summary_parts.append(f"{public_repos} public repositories")

                summary = "; ".join(summary_parts) + "."

                return {
                    "score": total_score,
                    "status": "success",
                    "summary": summary,
                    "details": {
                        "username": username,
                        "public_repos": public_repos,
                        "recent_events": recent_events_count,
                        "relevant_repos": matched_relevant,
                        "activity_score": activity_score,
                        "repo_score": repo_score,
                    },
                }

        except (httpx.TimeoutException, httpx.NetworkError):
            return {
                "score": 0,
                "status": "timeout",
                "summary": "GitHub API request timed out; safely recorded.",
                "details": {},
            }
        except Exception as e:
            return {
                "score": 0,
                "status": "error",
                "summary": f"GitHub enrichment error: {str(e)[:50]}",
                "details": {},
            }
