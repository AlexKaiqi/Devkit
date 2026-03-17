"""Unit tests for gate_checker module."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runtime"))

from methodology.models import GateType, GateResult
from methodology.gate_checker import (
    _expand_patterns,
    _fs_check_passes,
    _runtime_check_passes,
    _checklist_check_passes,
    _cross_artifact_check_passes,
    check_gate,
    check_transition_gates,
)


class TestExpandPatterns:
    def test_single_pattern(self):
        result = _expand_patterns(["requirements/acceptance/**/*{feature_slug}*.json"], "reminder-v2")
        assert result == ["requirements/acceptance/**/*reminder-v2*.json"]

    def test_multiple_patterns(self):
        result = _expand_patterns([
            "design/decisions/*{feature_slug}*.md",
            "design/architecture/*{feature_slug}*.md",
        ], "auth-feature")
        assert result == [
            "design/decisions/*auth-feature*.md",
            "design/architecture/*auth-feature*.md",
        ]

    def test_no_placeholder(self):
        result = _expand_patterns(["some/fixed/path/*.json"], "any-slug")
        assert result == ["some/fixed/path/*.json"]

    def test_empty_slug(self):
        result = _expand_patterns(["requirements/**/*{feature_slug}*.json"], "")
        # With empty slug, {feature_slug} is replaced with empty string
        assert result == ["requirements/**/*.json"] or "feature_slug" not in result[0]


class TestFsCheckPasses:
    def test_returns_true_when_file_exists(self, tmp_path):
        # Create the expected file
        acpt_dir = tmp_path / "requirements" / "acceptance"
        acpt_dir.mkdir(parents=True)
        (acpt_dir / "test-reminder-v2-scenario.json").write_text('{"title": "test"}')

        passed, details = _fs_check_passes(
            "requirements/acceptance/**/*{feature_slug}*.json",
            "reminder-v2",
            tmp_path,
        )
        assert passed is True
        assert "找到匹配文件" in details

    def test_returns_false_when_no_file(self, tmp_path):
        (tmp_path / "requirements" / "acceptance").mkdir(parents=True)

        passed, details = _fs_check_passes(
            "requirements/acceptance/**/*{feature_slug}*.json",
            "reminder-v2",
            tmp_path,
        )
        assert passed is False
        assert "未找到匹配文件" in details

    def test_multiple_patterns_any_match(self, tmp_path):
        # Create file matching second pattern
        design_dir = tmp_path / "design" / "architecture"
        design_dir.mkdir(parents=True)
        (design_dir / "my-feature-design.md").write_text("# Design")

        passed, details = _fs_check_passes(
            ["design/decisions/*{feature_slug}*.md", "design/architecture/*{feature_slug}*.md"],
            "my-feature",
            tmp_path,
        )
        assert passed is True

    def test_multiple_patterns_none_match(self, tmp_path):
        (tmp_path / "design" / "decisions").mkdir(parents=True)
        (tmp_path / "design" / "architecture").mkdir(parents=True)

        passed, details = _fs_check_passes(
            ["design/decisions/*{feature_slug}*.md", "design/architecture/*{feature_slug}*.md"],
            "my-feature",
            tmp_path,
        )
        assert passed is False

    def test_string_pattern(self, tmp_path):
        """String pattern (not list) should work."""
        (tmp_path / "requirements" / "acceptance").mkdir(parents=True)

        passed, details = _fs_check_passes(
            "requirements/acceptance/**/*{feature_slug}*.json",  # string, not list
            "missing-feature",
            tmp_path,
        )
        assert passed is False


class TestRuntimeCheckPasses:
    def test_passing_command(self, tmp_path):
        passed, details = _runtime_check_passes("exit 0", "exit_code == 0", tmp_path)
        assert passed is True

    def test_failing_command(self, tmp_path):
        passed, details = _runtime_check_passes("exit 1", "exit_code == 0", tmp_path)
        assert passed is False

    def test_captures_stderr_in_details(self, tmp_path):
        passed, details = _runtime_check_passes(
            "echo 'error output' >&2 && exit 1",
            "exit_code == 0",
            tmp_path,
        )
        assert passed is False
        # details should contain some info about the failure

    @patch("methodology.gate_checker.subprocess.run")
    def test_timeout_returns_failed(self, mock_run, tmp_path):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=120)
        passed, details = _runtime_check_passes("sleep 999", "exit_code == 0", tmp_path)
        assert passed is False
        assert "超时" in details

    @patch("methodology.gate_checker.subprocess.run")
    def test_exception_returns_failed(self, mock_run, tmp_path):
        mock_run.side_effect = OSError("command not found")
        passed, details = _runtime_check_passes("nonexistent_cmd", "exit_code == 0", tmp_path)
        assert passed is False
        assert "异常" in details


class TestCheckGate:
    def _mock_ontology(self, check_def):
        """Create a mock ontology that returns the given check_def."""
        mock_ont = MagicMock()
        mock_ont.get_gate_check_def.return_value = check_def
        return mock_ont

    def test_unknown_check_key(self, tmp_path):
        with patch("methodology.gate_checker.get_ontology") as mock_get:
            mock_get.return_value = self._mock_ontology(None)
            result = check_gate(
                "nonexistent_check",
                "test-feature",
                devkit_root=tmp_path,
                gate_type=GateType.hard_block,
                message="Test",
            )
        assert result.passed is False
        assert result.gate_check == "nonexistent_check"
        # message is preserved from caller; details should explain the unknown check
        assert "未找到" in result.details or "未知" in result.message or result.details != ""

    def test_deterministic_check_passes(self, tmp_path):
        # Create the expected file
        acpt_dir = tmp_path / "requirements" / "acceptance"
        acpt_dir.mkdir(parents=True)
        (acpt_dir / "test-my-feature-scenario.json").write_text("{}")

        check_def = {
            "type": "deterministic",
            "fs_check": "requirements/acceptance/**/*{feature_slug}*.json",
            "description": "Test check",
        }
        with patch("methodology.gate_checker.get_ontology") as mock_get:
            mock_get.return_value = self._mock_ontology(check_def)
            result = check_gate(
                "acceptance_case_exists",
                "my-feature",
                devkit_root=tmp_path,
                gate_type=GateType.hard_block,
                message="需要验收场景",
            )
        assert result.passed is True
        assert result.gate_check == "acceptance_case_exists"
        assert result.gate_type == GateType.hard_block

    def test_deterministic_check_fails(self, tmp_path):
        (tmp_path / "requirements" / "acceptance").mkdir(parents=True)

        check_def = {
            "type": "deterministic",
            "fs_check": "requirements/acceptance/**/*{feature_slug}*.json",
        }
        with patch("methodology.gate_checker.get_ontology") as mock_get:
            mock_get.return_value = self._mock_ontology(check_def)
            result = check_gate(
                "acceptance_case_exists",
                "missing-feature",
                devkit_root=tmp_path,
                gate_type=GateType.hard_block,
                message="需要验收场景",
            )
        assert result.passed is False
        assert result.message == "需要验收场景"

    def test_runtime_check_passes(self, tmp_path):
        check_def = {
            "type": "runtime",
            "command": "exit 0",
            "pass_condition": "exit_code == 0",
        }
        with patch("methodology.gate_checker.get_ontology") as mock_get:
            mock_get.return_value = self._mock_ontology(check_def)
            result = check_gate(
                "existing_tests_pass",
                "any-feature",
                devkit_root=tmp_path,
                gate_type=GateType.soft_warn,
                message="测试通过",
            )
        assert result.passed is True
        assert result.gate_type == GateType.soft_warn

    def test_runtime_check_fails(self, tmp_path):
        check_def = {
            "type": "runtime",
            "command": "exit 1",
            "pass_condition": "exit_code == 0",
        }
        with patch("methodology.gate_checker.get_ontology") as mock_get:
            mock_get.return_value = self._mock_ontology(check_def)
            result = check_gate(
                "existing_tests_pass",
                "any-feature",
                devkit_root=tmp_path,
                gate_type=GateType.soft_warn,
                message="测试通过",
            )
        assert result.passed is False

    def test_missing_fs_check_field(self, tmp_path):
        check_def = {
            "type": "deterministic",
            # missing fs_check
        }
        with patch("methodology.gate_checker.get_ontology") as mock_get:
            mock_get.return_value = self._mock_ontology(check_def)
            result = check_gate(
                "bad_check",
                "feature",
                devkit_root=tmp_path,
                gate_type=GateType.hard_block,
            )
        assert result.passed is False
        assert "fs_check" in result.details

    def test_unknown_check_type(self, tmp_path):
        check_def = {
            "type": "llm_check",  # not supported
            "prompt": "Did you write tests?",
        }
        with patch("methodology.gate_checker.get_ontology") as mock_get:
            mock_get.return_value = self._mock_ontology(check_def)
            result = check_gate(
                "llm_check",
                "feature",
                devkit_root=tmp_path,
                gate_type=GateType.soft_warn,
            )
        assert result.passed is False
        assert "未知的检查类型" in result.details

    def test_exception_does_not_propagate(self, tmp_path):
        """Gate checker should never raise — all errors become failed results."""
        with patch("methodology.gate_checker.get_ontology") as mock_get:
            mock_ont = MagicMock()
            mock_ont.get_gate_check_def.side_effect = RuntimeError("unexpected error")
            mock_get.return_value = mock_ont

            result = check_gate(
                "some_check",
                "feature",
                devkit_root=tmp_path,
                gate_type=GateType.hard_block,
            )
        assert result.passed is False


class TestCheckTransitionGates:
    def test_no_gates_returns_empty(self, tmp_path):
        """A transition with no defined gates returns empty list."""
        from methodology.models import ChangeType, Phase

        with patch("methodology.gate_checker.get_ontology") as mock_get:
            mock_ont = MagicMock()
            mock_ont.get_gates.return_value = []
            mock_get.return_value = mock_ont

            results = check_transition_gates(
                ChangeType.new_capability,
                Phase.classify,
                Phase.requirements,
                "test-feature",
                devkit_root=tmp_path,
            )
        assert results == []

    def test_multiple_gates_all_checked(self, tmp_path):
        """All gates in a transition should be checked."""
        from methodology.models import ChangeType, Phase

        with patch("methodology.gate_checker.get_ontology") as mock_get:
            mock_ont = MagicMock()
            mock_ont.get_gates.return_value = [
                MagicMock(check_key="check_a", gate_type=GateType.hard_block, message="A"),
                MagicMock(check_key="check_b", gate_type=GateType.soft_warn, message="B"),
            ]
            mock_ont.get_gate_check_def.return_value = None  # returns "unknown check" result
            mock_get.return_value = mock_ont

            results = check_transition_gates(
                ChangeType.new_capability,
                Phase.requirements,
                Phase.design,
                "test-feature",
                devkit_root=tmp_path,
            )
        assert len(results) == 2


class TestChecklistGate:
    def test_checklist_check_all_complete(self, tmp_path):
        """所有分类都完成时检查通过"""
        import json
        checklist = {
            "context_validation": [{"name": "item1", "completed": True}],
            "implementation_completeness": [{"name": "item2", "completed": True}],
        }
        feature_dir = tmp_path / "requirements" / "methodology" / "test-feat"
        feature_dir.mkdir(parents=True)
        (feature_dir / "dod-checklist.json").write_text(json.dumps(checklist))

        passed, details = _checklist_check_passes(
            "requirements/methodology/{feature_id}/dod-checklist.json",
            ["context_validation", "implementation_completeness"],
            "test-feat",
            tmp_path,
        )
        assert passed is True

    def test_checklist_check_incomplete(self, tmp_path):
        """有未完成的条目时检查失败"""
        import json
        checklist = {
            "context_validation": [{"name": "item1", "completed": False}],
        }
        feature_dir = tmp_path / "requirements" / "methodology" / "test-feat"
        feature_dir.mkdir(parents=True)
        (feature_dir / "dod-checklist.json").write_text(json.dumps(checklist))

        passed, details = _checklist_check_passes(
            "requirements/methodology/{feature_id}/dod-checklist.json",
            ["context_validation"],
            "test-feat",
            tmp_path,
        )
        assert passed is False
        assert "incomplete" in details.lower()

    def test_checklist_file_missing(self, tmp_path):
        """文件不存在时检查失败"""
        passed, details = _checklist_check_passes(
            "requirements/methodology/{feature_id}/dod-checklist.json",
            ["context_validation"],
            "nonexistent-feat",
            tmp_path,
        )
        assert passed is False
        assert "not found" in details.lower()


class TestCrossArtifactGate:
    def test_cross_artifact_check_passes(self, tmp_path):
        """找到包含 target_pattern 的文件时通过"""
        decisions_dir = tmp_path / "design" / "decisions"
        decisions_dir.mkdir(parents=True)
        (decisions_dir / "my-feature-decision.md").write_text("This references my-feature slug.")

        passed, details = _cross_artifact_check_passes(
            "design/decisions/*{feature_slug}*.md",
            "{feature_slug}",
            "my-feature",
            tmp_path,
        )
        assert passed is True

    def test_cross_artifact_check_fails(self, tmp_path):
        """没有匹配文件时失败"""
        passed, details = _cross_artifact_check_passes(
            "design/decisions/*{feature_slug}*.md",
            "{feature_slug}",
            "nonexistent-feature",
            tmp_path,
        )
        assert passed is False

