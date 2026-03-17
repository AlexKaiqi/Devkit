"""
Gate checker — executes gate check definitions against the filesystem or runtime.
Returns GateResult without raising exceptions.
"""

from __future__ import annotations

import glob
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

from methodology.models import GateResult, GateType
from methodology.ontology import get_ontology

log = logging.getLogger("methodology-gate-checker")

# Devkit root
_DEVKIT_ROOT = Path(__file__).resolve().parents[3]


def _expand_patterns(patterns: list[str], feature_slug: str) -> list[str]:
    """Replace {feature_slug} placeholder in glob patterns."""
    return [p.replace("{feature_slug}", feature_slug) for p in patterns]


def _fs_check_passes(
    fs_check: str | list[str],
    feature_slug: str,
    devkit_root: Path,
) -> tuple[bool, str]:
    """
    Check if any file matching the glob pattern exists.
    Returns (passed, details).
    """
    if isinstance(fs_check, str):
        patterns = [fs_check]
    else:
        patterns = list(fs_check)

    expanded = _expand_patterns(patterns, feature_slug)

    matched_files = []
    for pattern in expanded:
        full_pattern = str(devkit_root / pattern)
        matches = glob.glob(full_pattern, recursive=True)
        matched_files.extend(matches)

    if matched_files:
        rel_files = [str(Path(f).relative_to(devkit_root)) for f in matched_files[:3]]
        return True, f"找到匹配文件: {', '.join(rel_files)}"
    else:
        return False, f"未找到匹配文件（模式: {', '.join(expanded)}）"


def _runtime_check_passes(
    command: str,
    pass_condition: str,
    devkit_root: Path,
) -> tuple[bool, str]:
    """
    Run a command and check its exit code.
    Returns (passed, details).
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(devkit_root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        exit_code = result.returncode
        # Parse pass condition (currently only supports "exit_code == 0")
        if pass_condition == "exit_code == 0":
            passed = exit_code == 0
        else:
            log.warning("Unknown pass_condition: %s, defaulting to exit_code == 0", pass_condition)
            passed = exit_code == 0

        if passed:
            return True, f"命令执行成功 (exit_code={exit_code})"
        else:
            stderr_preview = (result.stderr or result.stdout or "")[:300]
            return False, f"命令执行失败 (exit_code={exit_code}): {stderr_preview}"

    except subprocess.TimeoutExpired:
        return False, "命令执行超时（120s）"
    except Exception as e:
        return False, f"命令执行异常: {e}"


def _checklist_check_passes(
    checklist_path_template: str,
    required_categories: list,
    feature_slug: str,
    devkit_root: Path,
) -> tuple[bool, str]:
    """检查 DoD 完成清单：所有 required 分类的条目均 completed=true"""
    path_str = checklist_path_template.replace("{feature_id}", feature_slug).replace("{feature_slug}", feature_slug)
    checklist_path = devkit_root / path_str
    if not checklist_path.exists():
        return False, f"Checklist file not found: {checklist_path}"
    try:
        data = json.loads(checklist_path.read_text())
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in checklist: {e}"

    missing = []
    for category in required_categories:
        items = data.get(category, [])
        if not items:
            missing.append(f"Category '{category}' is empty or missing")
            continue
        incomplete = [item for item in items if not item.get("completed", False)]
        if incomplete:
            missing.append(f"Category '{category}' has {len(incomplete)} incomplete item(s)")

    if missing:
        return False, "; ".join(missing)
    return True, "All required categories complete"


def _cross_artifact_check_passes(
    source_glob_template: str,
    target_pattern: str,
    feature_slug: str,
    devkit_root: Path,
) -> tuple[bool, str]:
    """检查 cross_artifact：source_glob 文件中包含 target_pattern"""
    import glob as glob_module
    expanded_glob = source_glob_template.replace("{feature_slug}", feature_slug)
    expanded_target = target_pattern.replace("{feature_slug}", feature_slug)

    matches = glob_module.glob(str(devkit_root / expanded_glob))
    if not matches:
        return False, f"No files matched glob: {expanded_glob}"

    for fpath in matches:
        try:
            content = Path(fpath).read_text()
            if expanded_target in content:
                return True, f"Found '{expanded_target}' in {fpath}"
        except Exception:
            continue

    return False, f"Pattern '{expanded_target}' not found in any matched files"


def _coverage_check_passes(
    command: str,
    coverage_report: str,
    min_coverage: float,
    devkit_root: Path,
) -> tuple[bool, str]:
    """运行测试并检查覆盖率"""
    result = subprocess.run(
        command.split(),
        cwd=str(devkit_root),
        capture_output=True,
        text=True,
        timeout=300,
    )

    report_path = devkit_root / coverage_report
    if not report_path.exists():
        return False, f"Coverage report not found: {report_path}"

    try:
        data = json.loads(report_path.read_text())
        percent = data.get("totals", {}).get("percent_covered", 0)
        if percent >= min_coverage:
            return True, f"Coverage {percent:.1f}% >= {min_coverage}%"
        return False, f"Coverage {percent:.1f}% < {min_coverage}%"
    except Exception as e:
        return False, f"Failed to parse coverage report: {e}"


def check_gate(
    check_key: str,
    feature_slug: str,
    devkit_root: Optional[Path] = None,
    gate_type: GateType = GateType.soft_warn,
    message: str = "",
) -> GateResult:
    """
    Execute a gate check and return a GateResult.
    Never raises exceptions — errors are captured as failed results.

    Args:
        check_key: The check identifier (e.g., "acceptance_case_exists")
        feature_slug: Feature identifier used in file glob patterns
        devkit_root: Root of the Devkit repo (defaults to auto-detected)
        gate_type: Type of gate (hard_block, soft_warn, skip_with_reason)
        message: Human-readable message for this gate
    """
    root = devkit_root or _DEVKIT_ROOT
    try:
        ontology = get_ontology()
        check_def = ontology.get_gate_check_def(check_key)
    except Exception as e:
        log.warning("Gate check %s raised exception during ontology lookup: %s", check_key, e)
        return GateResult(
            gate_check=check_key,
            passed=False,
            gate_type=gate_type,
            message=message,
            details=f"检查执行异常: {e}",
        )

    if check_def is None:
        return GateResult(
            gate_check=check_key,
            passed=False,
            gate_type=gate_type,
            message=message or f"未知的门控检查: {check_key}",
            details=f"在 gate-checks.yaml 中未找到 '{check_key}' 的定义",
        )

    template = check_def.get("template", "")
    check_type = check_def.get("type", "deterministic")

    try:
        if check_type == "deterministic":
            fs_check = check_def.get("fs_check")
            if fs_check is None:
                return GateResult(
                    gate_check=check_key,
                    passed=False,
                    gate_type=gate_type,
                    message=message,
                    details="gate-checks.yaml 中缺少 fs_check 字段",
                    template_path=template,
                )
            passed, details = _fs_check_passes(fs_check, feature_slug, root)

        elif check_type == "runtime":
            command = check_def.get("command", "")
            pass_condition = check_def.get("pass_condition", "exit_code == 0")
            if not command:
                return GateResult(
                    gate_check=check_key,
                    passed=False,
                    gate_type=gate_type,
                    message=message,
                    details="gate-checks.yaml 中缺少 command 字段",
                    template_path=template,
                )
            passed, details = _runtime_check_passes(command, pass_condition, root)

        elif check_type == "checklist":
            checklist_path = check_def.get("checklist_path", "")
            required_categories = check_def.get("required_categories", [])
            passed, details = _checklist_check_passes(checklist_path, required_categories, feature_slug, root)
            return GateResult(
                gate_check=check_key,
                passed=passed,
                gate_type=gate_type,
                message=message,
                details=details,
                template_path=template,
            )
        elif check_type == "cross_artifact":
            source_glob = check_def.get("source_glob", "")
            target_pattern = check_def.get("target_pattern", "")
            passed, details = _cross_artifact_check_passes(source_glob, target_pattern, feature_slug, root)
            return GateResult(
                gate_check=check_key,
                passed=passed,
                gate_type=gate_type,
                message=message,
                details=details,
                template_path=template,
            )
        elif check_type == "coverage":
            command = check_def.get("command", "")
            coverage_report = check_def.get("coverage_report", "coverage.json")
            min_coverage = check_def.get("min_coverage", 70)
            passed, details = _coverage_check_passes(command, coverage_report, min_coverage, root)
            return GateResult(
                gate_check=check_key,
                passed=passed,
                gate_type=gate_type,
                message=message,
                details=details,
                template_path=template,
            )

        else:
            return GateResult(
                gate_check=check_key,
                passed=False,
                gate_type=gate_type,
                message=message,
                details=f"未知的检查类型: {check_type}",
                template_path=template,
            )

        return GateResult(
            gate_check=check_key,
            passed=passed,
            gate_type=gate_type,
            message=message,
            details=details,
            template_path=template,
        )

    except Exception as e:
        log.warning("Gate check %s raised exception: %s", check_key, e)
        return GateResult(
            gate_check=check_key,
            passed=False,
            gate_type=gate_type,
            message=message,
            details=f"检查执行异常: {e}",
            template_path=template,
        )


def check_transition_gates(
    change_type,
    phase_from,
    phase_to,
    feature_slug: str,
    devkit_root: Optional[Path] = None,
) -> list[GateResult]:
    """
    Check all gates for a given phase transition.
    Returns list of GateResult for each gate.
    """
    ontology = get_ontology()
    gate_defs = ontology.get_gates(change_type, phase_from, phase_to)
    results = []
    for gate_def in gate_defs:
        result = check_gate(
            check_key=gate_def.check_key,
            feature_slug=feature_slug,
            devkit_root=devkit_root,
            gate_type=gate_def.gate_type,
            message=gate_def.message,
        )
        results.append(result)
    return results
