"""
Pydantic data models for Methodology Ontology Enforcement.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class ChangeType(str, Enum):
    new_capability = "new_capability"
    behavior_change = "behavior_change"
    bug_fix = "bug_fix"
    refactoring = "refactoring"
    doc_revision = "doc_revision"
    eval_asset = "eval_asset"


class Phase(str, Enum):
    classify = "classify"
    requirements = "requirements"
    design = "design"
    decomposition = "decomposition"
    implementation = "implementation"
    verification = "verification"
    asset_capture = "asset_capture"
    finalize = "finalize"


class GateType(str, Enum):
    hard_block = "hard_block"
    soft_warn = "soft_warn"
    skip_with_reason = "skip_with_reason"
    halt_condition = "halt_condition"


class Complexity(str, Enum):
    trivial = "trivial"
    standard = "standard"
    complex = "complex"


class SubPhase(str, Enum):
    change_point_analysis = "change_point_analysis"
    test_design = "test_design"
    code_implementation = "code_implementation"
    test_verification = "test_verification"


class GateCheckDef(BaseModel):
    name: str
    gate_type: GateType
    check_key: str
    message: str


class GateResult(BaseModel):
    gate_check: str
    passed: bool
    gate_type: GateType
    message: str = ""
    skip_reason: str = ""
    details: str = ""
    template_path: str = ""


class MandatoryPath(BaseModel):
    change_type: ChangeType
    phases: list[Phase]
    gates: dict[str, list[GateCheckDef]] = Field(default_factory=dict)
    # key format: "from_phase->to_phase"


class HaltCondition(BaseModel):
    """记录一个阻止流程继续的 halt 条件"""
    condition_id: str
    feature_id: str
    description: str
    phase: Phase
    resolved: bool = False
    created_at: str = ""
    resolved_at: str = ""
    notes: str = ""


class TestingStep(BaseModel):
    """测试策略中的单个步骤"""
    step: str
    action: str
    gate: Optional[str] = None
    is_hard_block: bool = False
    note: str = ""


class TestingStrategy(BaseModel):
    """某种 ChangeType 的测试策略"""
    change_type: str
    description: str
    required_approaches: list[str] = Field(default_factory=list)
    optional_approaches: list[str] = Field(default_factory=list)
    ordered_steps: list[TestingStep] = Field(default_factory=list)
    coverage_mandate: dict[str, Any] = Field(default_factory=dict)


class Feature(BaseModel):
    feature_id: str
    title: str
    change_type: ChangeType
    current_phase: Phase = Phase.classify
    status: str = "active"  # active | completed | abandoned
    session_key: str = ""
    skip_reasons: dict[str, str] = Field(default_factory=dict)  # phase -> reason
    created_at: str = ""
    updated_at: str = ""
    complexity: Complexity = Complexity.standard
    halt_conditions: list[HaltCondition] = Field(default_factory=list)
    sub_phase: Optional[SubPhase] = None


class InterceptResult(BaseModel):
    blocked: bool
    message: str = ""
    gate_results: list[GateResult] = Field(default_factory=list)
