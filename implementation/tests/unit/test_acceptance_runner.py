"""Unit tests for the acceptance runner scaffold."""

from pathlib import Path

import pytest

from implementation.evals.runners.acceptance_runner import (
    ValidationError,
    build_report,
    validate_case,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def make_case() -> dict:
    return {
        "id": "task-continuation-001",
        "title": "等待后的任务应以续作任务继续",
        "capability": "task-lifecycle",
        "scenario": "用户让系统稍后继续任务。",
        "input": {"user_message": "半小时后继续", "attachments": []},
        "expected": {
            "must": ["create_continuation_task"],
            "must_not": ["pretend_full_context_restore"],
        },
        "evidence": {"required": ["assistant_response", "task_record"]},
        "evaluation": {
            "mode": "hybrid",
            "deterministic_checks": ["continuation_task_created"],
            "llm_judge": {"rubric": "task_continuation_v1", "min_score": 4},
        },
    }


class TestValidateCase:

    def test_valid_case_passes(self):
        validate_case(make_case())

    def test_missing_key_fails(self):
        case = make_case()
        del case["scenario"]

        with pytest.raises(ValidationError):
            validate_case(case)

    def test_invalid_mode_fails(self):
        case = make_case()
        case["evaluation"]["mode"] = "magic"

        with pytest.raises(ValidationError):
            validate_case(case)


class TestBuildReport:

    def test_build_report_without_evidence(self):
        report = build_report(
            make_case(),
            REPO_ROOT / "requirements" / "acceptance" / "core" / "task-continuation-001.json",
        )

        assert report["status"] == "not_run"
        assert report["final_decision"] == "pending"
        assert report["deterministic_result"][0]["status"] == "pending"
        assert report["llm_judge_result"]["rubric"] == "task_continuation_v1"

    def test_build_report_with_evidence(self):
        report = build_report(
            make_case(),
            REPO_ROOT / "requirements" / "acceptance" / "core" / "task-continuation-001.json",
            evidence={"assistant_response": {}, "task_record": {}},
        )

        assert report["status"] == "evidence_loaded"
        assert sorted(report["evidence_summary"]) == ["assistant_response", "task_record"]
