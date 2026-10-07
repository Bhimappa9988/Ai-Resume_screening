import os
import json
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple

from src.config import config
from src.models import (
    ParsedResume,
    CandidateResult,
    ScoreBreakdown,
    BatchSummary,
    ScreeningResponse,
)
from src.parser import ResumeParser
from src.eligibility import EligibilityChecker
from src.github_enricher import GitHubEnricher
from src.llm_adapter import LLMAdapter
from src.scoring import CandidateScorer

logger = logging.getLogger(__name__)

class ResumeScreeningPipeline:
    """
    End-to-End Orchestrator for AI Resume Screening & Ranking.
    Ingests resumes, applies hard filters, enriches via GitHub & LLM,
    scores candidates against a 100-point rubric, and produces ranked shortlists.
    """

    def __init__(
        self,
        enable_github: bool = True,
        max_workers: int = 6,
    ):
        self.parser = ResumeParser()
        self.checker = EligibilityChecker()
        self.github_enricher = GitHubEnricher() if enable_github else None
        self.llm_adapter = LLMAdapter()
        self.scorer = CandidateScorer()
        self.max_workers = max_workers

    def process_single_resume(self, file_path: str) -> Tuple[Optional[CandidateResult], bool, Optional[str]]:
        """
        Process a single resume file.
        Returns:
            result: Optional[CandidateResult]
            is_parsed: bool
            error_msg: Optional[str]
        """
        path = Path(file_path)
        try:
            parsed = self.parser.parse_file(file_path)
        except Exception as e:
            logger.warning(f"Failed to parse resume {path.name}: {e}")
            return None, False, str(e)

        # 1. Hard Eligibility Filter
        is_eligible, rejection_reasons, py_evidence, ai_evidence = self.checker.check_eligibility(parsed)

        if not is_eligible:
            result = CandidateResult(
                rank=None,
                candidate_name=parsed.candidate_name,
                eligible=False,
                rejection_reasons=rejection_reasons,
                total_score=0,
                score_breakdown=ScoreBreakdown(),
                matched_skills=parsed.skills,
                project_summary="Profile did not meet minimum eligibility criteria.",
                github_summary="Skipped (ineligible candidate).",
                strengths=[],
                concerns=rejection_reasons,
                file_name=parsed.file_name,
                email=parsed.email,
                github_url=parsed.github_url,
            )
            return result, True, None

        # 2. GitHub Enrichment (if enabled and profile available)
        gh_enrichment = {"score": 0, "status": "disabled", "summary": "GitHub enrichment disabled."}
        if self.github_enricher:
            try:
                gh_enrichment = self.github_enricher.enrich(parsed.github_url or parsed.github_username)
            except Exception as e:
                gh_enrichment = {"score": 0, "status": "error", "summary": f"Enrichment error: {e}"}

        # 3. LLM / Heuristic Semantic Evaluation
        try:
            quality_assessment = self.llm_adapter.evaluate_candidate(parsed)
        except Exception as e:
            logger.warning(f"LLM evaluation failed for {parsed.candidate_name}: {e}. Falling back to heuristics.")
            quality_assessment = self.llm_adapter._heuristic_evaluation(parsed)

        # 4. 100-Point Scoring Model
        total_score, breakdown, strengths, concerns = self.scorer.score_candidate(
            parsed=parsed,
            github_enrichment=gh_enrichment,
            quality_assessment=quality_assessment,
        )

        result = CandidateResult(
            rank=None,  # Assigned after batch sorting
            candidate_name=parsed.candidate_name,
            eligible=True,
            rejection_reasons=[],
            total_score=total_score,
            score_breakdown=breakdown,
            matched_skills=parsed.skills,
            project_summary=quality_assessment.project_summary,
            github_summary=gh_enrichment.get("summary", ""),
            strengths=strengths,
            concerns=concerns,
            file_name=parsed.file_name,
            email=parsed.email,
            github_url=parsed.github_url,
        )

        return result, True, None

    def run_screening(self, input_dir: str) -> ScreeningResponse:
        """
        Execute screening over an entire folder of resumes.
        Handles bounded concurrency, ranking, and batch summary compilation.
        """
        input_path = Path(input_dir)
        if not input_path.exists() or not input_path.is_dir():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")

        resume_files = []
        for ext in ("*.pdf", "*.docx", "*.txt"):
            resume_files.extend(list(input_path.glob(ext)))

        total_resumes = len(resume_files)
        logger.info(f"Found {total_resumes} resumes in {input_dir}")

        parsed_count = 0
        failed_count = 0
        eligible_candidates: List[CandidateResult] = []
        rejected_candidates: List[CandidateResult] = []

        # Process resumes with bounded concurrency
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(self.process_single_resume, str(f)): f
                for f in resume_files
            }

            for future in as_completed(future_to_file):
                f_path = future_to_file[future]
                try:
                    result, is_parsed, error_msg = future.result()
                    if is_parsed and result:
                        parsed_count += 1
                        if result.eligible:
                            eligible_candidates.append(result)
                        else:
                            rejected_candidates.append(result)
                    else:
                        failed_count += 1
                        logger.warning(f"File {f_path.name} failed parsing: {error_msg}")
                except Exception as exc:
                    failed_count += 1
                    logger.error(f"Unhandled error processing {f_path.name}: {exc}")

        # Rank eligible candidates: highest score first; tie-breakers: ai_project_depth, python_backend
        eligible_candidates.sort(
            key=lambda c: (
                c.total_score,
                c.score_breakdown.ai_project_depth,
                c.score_breakdown.python_backend,
            ),
            reverse=True,
        )

        for idx, candidate in enumerate(eligible_candidates, start=1):
            candidate.rank = idx

        summary = BatchSummary(
            total_resumes=total_resumes,
            successfully_parsed=parsed_count,
            eligible=len(eligible_candidates),
            rejected=len(rejected_candidates),
            failed_unreadable=failed_count,
        )

        return ScreeningResponse(
            batch_summary=summary,
            ranked_candidates=eligible_candidates,
            rejected_candidates=rejected_candidates,
        )

    def export_results(
        self,
        response: ScreeningResponse,
        output_file: str,
        export_flat_list: bool = True,
    ) -> str:
        """
        Export screening results to a JSON file.
        Supports both the clean root list format shown in Section 7
        and the full metadata container.
        """
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Root list format specified in Assignment Section 7
        # Eligible candidates first (sorted by rank), followed by rejected candidates
        combined_list = [c.model_dump() for c in response.ranked_candidates] + [
            c.model_dump() for c in response.rejected_candidates
        ]

        # We save the primary array required by Section 7
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(combined_list, f, indent=2, ensure_ascii=False)

        # Also save an enriched summary file with the batch metadata
        summary_file = out_path.parent / f"{out_path.stem}_detailed.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(response.model_dump(), f, indent=2, ensure_ascii=False)

        return str(out_path.resolve())

    def export_html_report(self, response: ScreeningResponse, html_file: str) -> str:
        """Generate a clean, standalone visual HTML report of the screening results."""
        out_path = Path(html_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        rows = ""
        for c in response.ranked_candidates:
            rows += f"""
            <tr class="eligible-row">
                <td class="rank-col">#{c.rank}</td>
                <td class="name-col">
                    <strong>{c.candidate_name}</strong>
                    <div class="meta">{c.email or ''} | {c.file_name or ''}</div>
                </td>
                <td><span class="badge score-badge">{c.total_score} / 100</span></td>
                <td><span class="pill ai-pill">{c.score_breakdown.ai_project_depth}/40</span></td>
                <td><span class="pill py-pill">{c.score_breakdown.python_backend}/30</span></td>
                <td><span class="pill cloud-pill">{c.score_breakdown.cloud_fullstack}/15</span></td>
                <td><span class="pill gh-pill">{c.score_breakdown.github}/10</span></td>
                <td><span class="pill eng-pill">{c.score_breakdown.engineering_depth}/5</span></td>
                <td class="summary-col">{c.project_summary}</td>
                <td><div class="skills-cell">{' '.join([f'<span class="skill-tag">{s}</span>' for s in c.matched_skills[:6]])}</div></td>
            </tr>
            """

        rejected_rows = ""
        for c in response.rejected_candidates:
            reasons = "<br>".join(c.rejection_reasons)
            rejected_rows += f"""
            <tr class="rejected-row">
                <td>-</td>
                <td><strong>{c.candidate_name}</strong><div class="meta">{c.file_name or ''}</div></td>
                <td><span class="badge reject-badge">REJECTED</span></td>
                <td colspan="5" class="reason-cell">{reasons}</td>
                <td colspan="2"><div class="skills-cell">{' '.join([f'<span class="skill-tag">{s}</span>' for s in c.matched_skills[:5]])}</div></td>
            </tr>
            """

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AI Resume Screening & Ranking Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; color: #1e293b; margin: 0; padding: 24px; }}
        .header {{ background: #0f172a; color: white; padding: 28px; border-radius: 12px; margin-bottom: 24px; }}
        h1 {{ margin: 0 0 8px 0; font-size: 26px; }}
        .subtitle {{ color: #94a3b8; font-size: 14px; margin: 0; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }}
        .stat-card {{ background: white; padding: 18px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; }}
        .stat-val {{ font-size: 28px; font-weight: 700; color: #0f172a; margin-top: 4px; }}
        .stat-card.eligible .stat-val {{ color: #16a34a; }}
        .stat-card.rejected .stat-val {{ color: #dc2626; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; border: 1px solid #e2e8f0; margin-bottom: 28px; }}
        th, td {{ padding: 12px 14px; text-align: left; font-size: 13px; border-bottom: 1px solid #f1f5f9; }}
        th {{ background: #f8fafc; font-weight: 600; color: #475569; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; }}
        .rank-col {{ font-weight: 700; font-size: 16px; color: #2563eb; width: 45px; }}
        .badge {{ display: inline-block; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 12px; }}
        .score-badge {{ background: #dbeafe; color: #1e40af; }}
        .reject-badge {{ background: #fee2e2; color: #991b1b; }}
        .pill {{ display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
        .ai-pill {{ background: #f3e8ff; color: #7e22ce; }}
        .py-pill {{ background: #e0f2fe; color: #0369a1; }}
        .cloud-pill {{ background: #fef3c7; color: #b45309; }}
        .gh-pill {{ background: #f1f5f9; color: #334155; }}
        .eng-pill {{ background: #dcfce7; color: #15803d; }}
        .skill-tag {{ display: inline-block; background: #f1f5f9; color: #334155; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin: 2px; }}
        .meta {{ font-size: 11px; color: #64748b; margin-top: 3px; }}
        .summary-col {{ max-width: 280px; color: #334155; }}
        .reason-cell {{ color: #b91c1c; font-weight: 500; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>AI Resume Screening & Ranking System</h1>
        <p class="subtitle">SDE Intern (Python + AI) Evaluation Shortlist & Score Breakdown</p>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div>Total Ingested</div>
            <div class="stat-val">{response.batch_summary.total_resumes}</div>
        </div>
        <div class="stat-card">
            <div>Successfully Parsed</div>
            <div class="stat-val">{response.batch_summary.successfully_parsed}</div>
        </div>
        <div class="stat-card eligible">
            <div>Eligible Shortlist</div>
            <div class="stat-val">{response.batch_summary.eligible}</div>
        </div>
        <div class="stat-card rejected">
            <div>Hard Filter Rejected</div>
            <div class="stat-val">{response.batch_summary.rejected}</div>
        </div>
    </div>

    <h2>Eligible Candidates Shortlist (Ranked)</h2>
    <table>
        <thead>
            <tr>
                <th>Rank</th>
                <th>Candidate</th>
                <th>Total</th>
                <th>AI Depth (40)</th>
                <th>Python (30)</th>
                <th>Cloud (15)</th>
                <th>GitHub (10)</th>
                <th>Eng (5)</th>
                <th>Project Summary</th>
                <th>Skills</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>

    <h2>Disqualified Candidates (Hard Filter Rejections)</h2>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Candidate</th>
                <th>Status</th>
                <th colspan="5">Rejection Reasons</th>
                <th colspan="2">Detected Skills</th>
            </tr>
        </thead>
        <tbody>
            {rejected_rows}
        </tbody>
    </table>
</body>
</html>
"""
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return str(out_path.resolve())
