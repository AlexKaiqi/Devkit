"""
CLI tool for methodology gate checking.

Usage:
    .venv/bin/python -m implementation.runtime.methodology.cli check \
        --feature reminder-v2 --change-type new_capability

    .venv/bin/python -m implementation.runtime.methodology.cli list-change-types
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add runtime to path
_RUNTIME_DIR = Path(__file__).resolve().parents[1]
if str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))

from methodology.models import ChangeType, Phase, GateType
from methodology.ontology import get_ontology
from methodology.gate_checker import check_transition_gates


def _symbol(passed: bool, gate_type: GateType) -> str:
    if passed:
        return "✅"
    if gate_type == GateType.hard_block:
        return "⛔"
    return "⚠️ "


def cmd_check(args) -> int:
    """Check methodology gates for a given feature."""
    feature_slug = args.feature
    try:
        change_type = ChangeType(args.change_type)
    except ValueError:
        print(f"❌ 未知 change-type: {args.change_type}")
        print(f"   可用值: {', '.join(ct.value for ct in ChangeType)}")
        return 1

    ontology = get_ontology()
    path = ontology.get_mandatory_path(change_type)
    if not path:
        print(f"❌ 未找到 {change_type.value} 的强制路径定义")
        return 1

    current_phase = Phase(args.current_phase) if args.current_phase else None

    print(f"\n方法论检查: Feature={feature_slug}  ChangeType={change_type.value}")
    print("─" * 60)

    phases = path.phases
    any_blocked = False

    for i, phase in enumerate(phases):
        # Determine phase status
        if current_phase:
            if phase == current_phase:
                phase_status = "current"
            elif phases.index(phase) < phases.index(current_phase):
                phase_status = "done"
            else:
                phase_status = "pending"
        else:
            phase_status = "unknown"

        if phase_status == "done":
            print(f"  ✅ {phase.value}")
        elif phase_status == "current":
            print(f"  ▶  {phase.value} ← 当前阶段")
        else:
            print(f"  ⏸  {phase.value}")

        # Check gates from this phase to next
        if i + 1 < len(phases):
            next_phase = phases[i + 1]
            gate_defs = ontology.get_gates(change_type, phase, next_phase)
            if gate_defs:
                results = check_transition_gates(
                    change_type, phase, next_phase, feature_slug
                )
                for result in results:
                    sym = _symbol(result.passed, result.gate_type)
                    status = "通过" if result.passed else "未通过"
                    if not result.passed:
                        if result.gate_type == GateType.hard_block:
                            any_blocked = True
                        print(f"    {sym} 门控 {phase.value}→{next_phase.value}: "
                              f"{result.gate_check} [{status}]")
                        if not result.passed and result.message:
                            print(f"       需要: {result.message}")
                        if result.details:
                            print(f"       详情: {result.details}")
                    else:
                        print(f"    {sym} 门控 {phase.value}→{next_phase.value}: "
                              f"{result.gate_check} [{status}]")
                        if result.details:
                            print(f"       详情: {result.details}")

    print("─" * 60)
    if any_blocked:
        print("⛔ 存在未通过的 hard_block 门控，无法推进到下一阶段\n")
        return 2
    else:
        print("✅ 所有 hard_block 门控通过\n")
        return 0


def cmd_list_change_types(args) -> int:
    """List all available change types."""
    ontology = get_ontology()
    print("\n可用的 ChangeType:")
    for ct in ontology.list_change_types():
        path = ontology.get_mandatory_path(ct)
        phases_str = " → ".join(p.value for p in path.phases) if path else "N/A"
        print(f"  {ct.value:20s}  {phases_str}")
    print()
    return 0


def cmd_show_path(args) -> int:
    """Show the mandatory path for a given change type."""
    try:
        change_type = ChangeType(args.change_type)
    except ValueError:
        print(f"❌ 未知 change-type: {args.change_type}")
        return 1

    ontology = get_ontology()
    path = ontology.get_mandatory_path(change_type)
    if not path:
        print(f"❌ 未找到 {change_type.value} 的路径定义")
        return 1

    print(f"\n{change_type.value} 强制路径:")
    phases = path.phases
    for i, phase in enumerate(phases):
        print(f"  [{i+1}] {phase.value}")
        if i + 1 < len(phases):
            next_phase = phases[i + 1]
            gate_defs = ontology.get_gates(change_type, phase, next_phase)
            for gd in gate_defs:
                sym = "⛔" if gd.gate_type == GateType.hard_block else "⚠️ "
                print(f"      {sym} [{gd.gate_type.value}] {gd.check_key}")
                print(f"         {gd.message}")
    print()
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="方法论门控检查工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 检查 feature 的门控状态
  .venv/bin/python -m implementation.runtime.methodology.cli check \\
      --feature reminder-v2 --change-type new_capability

  # 检查时指定当前阶段
  .venv/bin/python -m implementation.runtime.methodology.cli check \\
      --feature reminder-v2 --change-type new_capability --current-phase requirements

  # 查看所有 ChangeType
  .venv/bin/python -m implementation.runtime.methodology.cli list-change-types

  # 查看特定 ChangeType 的路径
  .venv/bin/python -m implementation.runtime.methodology.cli show-path \\
      --change-type new_capability
        """,
    )
    subparsers = parser.add_subparsers(dest="command")

    # check
    check_parser = subparsers.add_parser("check", help="检查 Feature 门控状态")
    check_parser.add_argument("--feature", "-f", required=True,
                               help="Feature slug（用于文件系统搜索，如 reminder-v2）")
    check_parser.add_argument("--change-type", "-t", required=True,
                               help=f"变更类型（{', '.join(ct.value for ct in ChangeType)}）")
    check_parser.add_argument("--current-phase", "-p", default=None,
                               help="当前阶段（可选，用于高亮显示）")

    # list-change-types
    subparsers.add_parser("list-change-types", help="列出所有 ChangeType")

    # show-path
    path_parser = subparsers.add_parser("show-path", help="显示 ChangeType 的强制路径")
    path_parser.add_argument("--change-type", "-t", required=True, help="变更类型")

    args = parser.parse_args()

    if args.command == "check":
        sys.exit(cmd_check(args))
    elif args.command == "list-change-types":
        sys.exit(cmd_list_change_types(args))
    elif args.command == "show-path":
        sys.exit(cmd_show_path(args))
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
