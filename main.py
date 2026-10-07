import argparse
import sys
import logging
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.pipeline import ResumeScreeningPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ScreeningSystem")

def main():
    parser = argparse.ArgumentParser(
        description="AI Resume Screening & Ranking System for SDE Interns (Python + AI)"
    )
    parser.add_argument(
        "--input",
        "-i",
        default="./resumes",
        help="Path to folder containing candidate resumes (PDF/DOCX/TXT)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="./output/results.json",
        help="Path for generated JSON results",
    )
    parser.add_argument(
        "--html",
        default="./output/report.html",
        help="Path for optional visual HTML report",
    )
    parser.add_argument(
        "--no-github",
        action="store_true",
        help="Disable public GitHub enrichment calls",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=6,
        help="Number of concurrent worker threads",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("      AI RESUME SCREENING & RANKING SYSTEM (SDE INTERN)      ")
    print("=" * 70)
    print(f"Input Directory  : {args.input}")
    print(f"Output File      : {args.output}")
    print(f"HTML Report      : {args.html}")
    print(f"GitHub Enrichment: {'Disabled' if args.no_github else 'Enabled'}")
    print(f"Worker Threads   : {args.workers}")
    print("-" * 70)

    pipeline = ResumeScreeningPipeline(
        enable_github=not args.no_github,
        max_workers=args.workers,
    )

    try:
        response = pipeline.run_screening(args.input)
    except Exception as e:
        logger.error(f"Failed to execute screening pipeline: {e}")
        sys.exit(1)

    json_path = pipeline.export_results(response, args.output)
    html_path = pipeline.export_html_report(response, args.html)

    summary = response.batch_summary
    print("\n" + "=" * 70)
    print("                      BATCH PROCESSING SUMMARY                        ")
    print("=" * 70)
    print(f"Total Resumes Ingested : {summary.total_resumes}")
    print(f"Successfully Parsed    : {summary.successfully_parsed}")
    print(f"Eligible Candidates    : {summary.eligible}")
    print(f"Rejected Candidates    : {summary.rejected}")
    print(f"Malformed / Unreadable : {summary.failed_unreadable}")
    print("=" * 70)

    print("\n" + "-" * 70)
    print(f"{'RANK':<5} | {'CANDIDATE NAME':<24} | {'SCORE':<6} | {'AI/40':<6} | {'PY/30':<6} | {'GH/10':<6}")
    print("-" * 70)
    for c in response.ranked_candidates[:15]:
        print(
            f"#{c.rank:<4} | {c.candidate_name[:24]:<24} | "
            f"{c.total_score:<6} | {c.score_breakdown.ai_project_depth:<6} | "
            f"{c.score_breakdown.python_backend:<6} | {c.score_breakdown.github:<6}"
        )

    if len(response.ranked_candidates) > 15:
        print(f"... and {len(response.ranked_candidates) - 15} more eligible candidates.")

    print("-" * 70)
    print(f"[+] Output JSON saved to : {json_path}")
    print(f"[+] HTML Report saved to: {html_path}")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
