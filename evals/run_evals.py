#!/usr/bin/env python
"""Run evaluation suite and generate reports."""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

EVALS_DIR = Path(__file__).parent
PROJECT_ROOT = EVALS_DIR.parent
REPORTS_DIR = EVALS_DIR / "reports"


def run_pytest(
    test_files: list[str] | None = None,
    markers: str | None = None,
    verbose: bool = False,
    generate_report: bool = True,
) -> tuple[int, str]:
    """Run pytest with specified options.

    Returns:
        Tuple of (exit_code, report_path)
    """
    # Ensure reports directory exists
    REPORTS_DIR.mkdir(exist_ok=True)

    # Build pytest command
    cmd = [sys.executable, "-m", "pytest"]

    # Add test files or default to evals directory
    if test_files:
        cmd.extend(test_files)
    else:
        cmd.append(str(EVALS_DIR))

    # Add markers filter
    if markers:
        cmd.extend(["-m", markers])

    # Verbosity
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    # Generate reports
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"eval_report_{timestamp}"

    if generate_report:
        # JUnit XML report
        cmd.extend([f"--junitxml={report_path}.xml"])
        # HTML report (if pytest-html is installed)
        cmd.extend([f"--html={report_path}.html", "--self-contained-html"])

    # Run pytest
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    return result.returncode, str(report_path)


def run_sentiment_evals(verbose: bool = False) -> int:
    """Run sentiment analysis evaluations."""
    print("\n" + "=" * 60)
    print("SENTIMENT ANALYSIS EVALUATIONS")
    print("=" * 60)

    exit_code, _ = run_pytest(
        test_files=[str(EVALS_DIR / "test_sentiment.py")],
        verbose=verbose,
    )
    return exit_code


def run_suggestion_evals(verbose: bool = False) -> int:
    """Run smart suggestion evaluations."""
    print("\n" + "=" * 60)
    print("SMART SUGGESTIONS EVALUATIONS")
    print("=" * 60)

    exit_code, _ = run_pytest(
        test_files=[str(EVALS_DIR / "test_smart_suggestions.py")],
        verbose=verbose,
    )
    return exit_code


def run_api_evals(verbose: bool = False) -> int:
    """Run API endpoint evaluations."""
    print("\n" + "=" * 60)
    print("API EVALUATIONS")
    print("=" * 60)

    exit_code, _ = run_pytest(
        test_files=[
            str(EVALS_DIR / "test_canned_responses.py"),
            str(EVALS_DIR / "test_customer_context.py"),
        ],
        verbose=verbose,
    )
    return exit_code


def run_integration_evals(verbose: bool = False) -> int:
    """Run integration evaluations."""
    print("\n" + "=" * 60)
    print("INTEGRATION EVALUATIONS")
    print("=" * 60)

    exit_code, _ = run_pytest(
        test_files=[str(EVALS_DIR / "test_integration.py")],
        verbose=verbose,
    )
    return exit_code


def run_quick_evals(verbose: bool = False) -> int:
    """Run quick evaluations (no API calls)."""
    print("\n" + "=" * 60)
    print("QUICK EVALUATIONS (No API calls)")
    print("=" * 60)

    # Run tests that don't require API keys
    exit_code, _ = run_pytest(
        markers="not skip_no_api_key",
        verbose=verbose,
    )
    return exit_code


def run_all_evals(verbose: bool = False) -> int:
    """Run all evaluations."""
    print("\n" + "=" * 60)
    print("FULL EVALUATION SUITE")
    print("=" * 60)

    exit_code, report_path = run_pytest(verbose=verbose)

    print(f"\nReports generated at: {report_path}.*")
    return exit_code


def generate_summary_report():
    """Generate a summary of the latest evaluation run."""
    # Find the latest XML report
    reports = list(REPORTS_DIR.glob("eval_report_*.xml"))
    if not reports:
        print("No reports found. Run evaluations first.")
        return

    latest_report = max(reports, key=lambda p: p.stat().st_mtime)

    # Parse XML report
    import xml.etree.ElementTree as ET
    tree = ET.parse(latest_report)
    root = tree.getroot()

    # Extract statistics
    testsuite = root.find("testsuite") or root
    stats = {
        "tests": int(testsuite.get("tests", 0)),
        "failures": int(testsuite.get("failures", 0)),
        "errors": int(testsuite.get("errors", 0)),
        "skipped": int(testsuite.get("skipped", 0)),
        "time": float(testsuite.get("time", 0)),
    }
    stats["passed"] = stats["tests"] - stats["failures"] - stats["errors"] - stats["skipped"]

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Report: {latest_report.name}")
    print(f"Total Tests: {stats['tests']}")
    print(f"  Passed: {stats['passed']}")
    print(f"  Failed: {stats['failures']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Skipped: {stats['skipped']}")
    print(f"Time: {stats['time']:.2f}s")

    # Calculate pass rate
    if stats["tests"] > 0:
        pass_rate = (stats["passed"] / (stats["tests"] - stats["skipped"])) * 100 if (stats["tests"] - stats["skipped"]) > 0 else 0
        print(f"Pass Rate: {pass_rate:.1f}%")

    # List failures
    failures = testsuite.findall(".//failure") + testsuite.findall(".//error")
    if failures:
        print("\nFailures:")
        for failure in failures[:5]:  # Show first 5 failures
            testcase = failure.getparent() if hasattr(failure, 'getparent') else None
            if testcase is not None:
                print(f"  - {testcase.get('classname', '')}.{testcase.get('name', '')}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Run CX Agent evaluations")
    parser.add_argument(
        "suite",
        nargs="?",
        choices=["all", "quick", "sentiment", "suggestions", "api", "integration", "summary"],
        default="all",
        help="Evaluation suite to run (default: all)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Don't generate HTML/XML reports",
    )

    args = parser.parse_args()

    # Check for required environment
    if args.suite not in ["quick", "api", "summary"]:
        if not os.getenv("LLM_API_KEY"):
            print("Warning: LLM_API_KEY not set. AI-powered tests will be skipped.")
            print("Set the environment variable or run 'quick' suite for non-API tests.\n")

    # Run selected suite
    if args.suite == "summary":
        generate_summary_report()
        return 0
    elif args.suite == "all":
        exit_code = run_all_evals(verbose=args.verbose)
    elif args.suite == "quick":
        exit_code = run_quick_evals(verbose=args.verbose)
    elif args.suite == "sentiment":
        exit_code = run_sentiment_evals(verbose=args.verbose)
    elif args.suite == "suggestions":
        exit_code = run_suggestion_evals(verbose=args.verbose)
    elif args.suite == "api":
        exit_code = run_api_evals(verbose=args.verbose)
    elif args.suite == "integration":
        exit_code = run_integration_evals(verbose=args.verbose)

    # Generate summary
    if exit_code == 0:
        print("\n All evaluations passed!")
    else:
        print(f"\n Some evaluations failed (exit code: {exit_code})")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
