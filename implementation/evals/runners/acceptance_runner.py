"""Acceptance runner scaffold for requirement-layer cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPORT_DIR = REPO_ROOT / "implementation" / "evals" / "reports"
REQUIRED_TOP_LEVEL_KEYS = {
    "id",
    "title",
    "capability",
    "scenario",
    "input",
    "expected",
    "evidence",
    "evaluation",
}
REQUIRED_EVALUATION_KEYS = {"mode", "deterministic_checks"}


class ValidationError(ValueError):
    """Raised when an acceptance case is malformed."""


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_case(case: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - case.keys())
    if missing:
        raise ValidationError(f"Missing top-level keys: {', '.join(missing)}")

    if not isinstance(case["expected"], dict):
        raise ValidationError("'expected' must be an object")
    if not isinstance(case["evaluation"], dict):
        raise ValidationError("'evaluation' must be an object")

    evaluation_missing = sorted(REQUIRED_EVALUATION_KEYS - case["evaluation"].keys())
    if evaluation_missing:
        raise ValidationError(
            "Missing evaluation keys: " + ", ".join(evaluation_missing)
        )

    if case["evaluation"]["mode"] not in {"deterministic", "llm", "hybrid"}:
        raise ValidationError("evaluation.mode must be deterministic, llm, or hybrid")

    if not isinstance(case["evaluation"]["deterministic_checks"], list):
        raise ValidationError("evaluation.deterministic_checks must be a list")

    llm_judge = case["evaluation"].get("llm_judge")
    if llm_judge is not None and not isinstance(llm_judge, dict):
        raise ValidationError("evaluation.llm_judge must be an object when present")


def build_report(
    case: dict[str, Any],
    case_path: Path,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    llm_judge = case["evaluation"].get("llm_judge")
    return {
        "case_id": case["id"],
        "title": case["title"],
        "case_path": str(case_path.relative_to(REPO_ROOT)),
        "status": "evidence_loaded" if evidence else "not_run",
        "scenario": case["scenario"],
        "evaluation_mode": case["evaluation"]["mode"],
        "deterministic_result": [
            {"name": name, "status": "pending"}
            for name in case["evaluation"]["deterministic_checks"]
        ],
        "llm_judge_result": (
            {
                "rubric": llm_judge.get("rubric", ""),
                "min_score": llm_judge.get("min_score"),
                "status": "pending",
            }
            if llm_judge
            else None
        ),
        "final_decision": "pending",
        "required_evidence": case["evidence"].get("required", []),
        "evidence_summary": sorted(evidence.keys()) if evidence else [],
    }


def write_report(report: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Acceptance runner scaffold")
    parser.add_argument(
        "--case",
        required=True,
        help="Path to a JSON acceptance case under requirements/acceptance/",
    )
    parser.add_argument(
        "--evidence",
        help="Optional path to a JSON evidence bundle",
    )
    parser.add_argument(
        "--output",
        help="Optional output report path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    case_path = Path(args.case).expanduser()
    if not case_path.is_absolute():
        case_path = REPO_ROOT / case_path

    case = load_json(case_path)
    validate_case(case)

    evidence = None
    if args.evidence:
        evidence_path = Path(args.evidence).expanduser()
        if not evidence_path.is_absolute():
            evidence_path = REPO_ROOT / evidence_path
        evidence = load_json(evidence_path)

    report = build_report(case, case_path, evidence=evidence)

    if args.output:
        output_path = Path(args.output).expanduser()
        if not output_path.is_absolute():
            output_path = REPO_ROOT / output_path
    else:
        output_path = DEFAULT_REPORT_DIR / f"{case['id']}.json"

    write_report(report, output_path)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
