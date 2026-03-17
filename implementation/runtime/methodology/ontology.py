"""
Ontology loader — loads methodology.yaml and gate-checks.yaml,
provides query interface for mandatory paths and gate definitions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

from methodology.models import (
    ChangeType,
    Phase,
    GateType,
    GateCheckDef,
    GateResult,
    MandatoryPath,
)

log = logging.getLogger("methodology-ontology")

# Paths relative to devkit root
_ONTOLOGY_DIR = Path(__file__).resolve().parents[3] / "design" / "ontology"
_METHODOLOGY_YAML = _ONTOLOGY_DIR / "methodology.yaml"
_GATE_CHECKS_YAML = _ONTOLOGY_DIR / "gate-checks.yaml"
_TESTING_YAML = _ONTOLOGY_DIR / "testing-methodology.yaml"
_COMPLEXITY_YAML = _ONTOLOGY_DIR / "complexity-tracks.yaml"


class _Ontology:
    """Lazily loaded ontology singleton."""

    def __init__(self):
        self._loaded = False
        self._methodology: dict = {}
        self._gate_checks: dict = {}
        self._testing: dict = {}
        self._complexity: dict = {}
        self._paths: dict[ChangeType, MandatoryPath] = {}

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        try:
            with open(_METHODOLOGY_YAML, "r", encoding="utf-8") as f:
                self._methodology = yaml.safe_load(f)
        except Exception as e:
            log.error("Failed to load methodology.yaml: %s", e)
            self._methodology = {}

        try:
            with open(_GATE_CHECKS_YAML, "r", encoding="utf-8") as f:
                self._gate_checks = yaml.safe_load(f) or {}
        except Exception as e:
            log.error("Failed to load gate-checks.yaml: %s", e)
            self._gate_checks = {}

        try:
            with open(_TESTING_YAML, "r", encoding="utf-8") as f:
                self._testing = yaml.safe_load(f) or {}
        except Exception as e:
            log.warning("Failed to load testing-methodology.yaml: %s", e)
            self._testing = {}

        try:
            with open(_COMPLEXITY_YAML, "r", encoding="utf-8") as f:
                self._complexity = yaml.safe_load(f) or {}
        except Exception as e:
            log.warning("Failed to load complexity-tracks.yaml: %s", e)
            self._complexity = {}

        self._parse_paths()
        self._loaded = True
        log.info("Methodology ontology loaded: %d change types", len(self._paths))

    def _parse_paths(self) -> None:
        """Parse mandatory_paths from YAML into MandatoryPath objects."""
        raw_paths = self._methodology.get("mandatory_paths", {})
        for ct_str, path_data in raw_paths.items():
            try:
                change_type = ChangeType(ct_str)
            except ValueError:
                log.warning("Unknown ChangeType in methodology.yaml: %s", ct_str)
                continue

            phases = []
            for p_str in path_data.get("phases", []):
                try:
                    phases.append(Phase(p_str))
                except ValueError:
                    log.warning("Unknown Phase: %s", p_str)

            gates: dict[str, list[GateCheckDef]] = {}
            raw_gates = path_data.get("gates", {}) or {}
            for transition, checks in raw_gates.items():
                if not checks:
                    continue
                gate_list = []
                for check in checks:
                    try:
                        gate_type = GateType(check.get("type", "soft_warn"))
                        check_key = check.get("check", "")
                        message = check.get("message", "")
                        gate_def = GateCheckDef(
                            name=check_key,
                            gate_type=gate_type,
                            check_key=check_key,
                            message=message,
                        )
                        gate_list.append(gate_def)
                    except Exception as e:
                        log.warning("Failed to parse gate check %s: %s", check, e)
                if gate_list:
                    gates[transition] = gate_list

            self._paths[change_type] = MandatoryPath(
                change_type=change_type,
                phases=phases,
                gates=gates,
            )

    def get_mandatory_path(self, change_type: ChangeType) -> Optional[MandatoryPath]:
        """Return the mandatory path for a given ChangeType."""
        self._ensure_loaded()
        return self._paths.get(change_type)

    def get_gates(
        self,
        change_type: ChangeType,
        phase_from: Phase,
        phase_to: Phase,
    ) -> list[GateCheckDef]:
        """Return gate definitions for a specific phase transition."""
        self._ensure_loaded()
        path = self._paths.get(change_type)
        if not path:
            return []
        key = f"{phase_from.value}->{phase_to.value}"
        return path.gates.get(key, [])

    def get_next_phase(
        self,
        change_type: ChangeType,
        current_phase: Phase,
    ) -> Optional[Phase]:
        """Return the next required phase after current_phase."""
        self._ensure_loaded()
        path = self._paths.get(change_type)
        if not path:
            return None
        phases = path.phases
        try:
            idx = phases.index(current_phase)
        except ValueError:
            return None
        if idx + 1 >= len(phases):
            return None
        return phases[idx + 1]

    def is_phase_required(self, change_type: ChangeType, phase: Phase) -> bool:
        """Return True if the phase is in the mandatory path for this ChangeType."""
        self._ensure_loaded()
        path = self._paths.get(change_type)
        if not path:
            return False
        return phase in path.phases

    def get_gate_check_def(self, check_key: str) -> Optional[dict]:
        """Return the gate check definition from gate-checks.yaml."""
        self._ensure_loaded()
        checks = self._gate_checks.get("gate_checks", {})
        return checks.get(check_key)

    def list_change_types(self) -> list[ChangeType]:
        """Return all known ChangeTypes."""
        self._ensure_loaded()
        return list(self._paths.keys())

    def get_testing_strategy(self, change_type_str: str) -> Optional[dict]:
        """Return testing strategy for a ChangeType from testing-methodology.yaml."""
        self._ensure_loaded()
        strategies = self._testing.get("testing_strategies", {})
        return strategies.get(change_type_str)

    def get_complexity_rules(self, complexity_str: str) -> Optional[dict]:
        """Return complexity rules from complexity-tracks.yaml."""
        self._ensure_loaded()
        rules = self._complexity.get("complexity_rules", {})
        return rules.get(complexity_str)

    def list_testing_approaches(self) -> list[str]:
        """Return all defined testing approach instances."""
        self._ensure_loaded()
        classes = self._testing.get("classes", {})
        approach_class = classes.get("TestingApproach", {})
        return approach_class.get("instances", [])


# Module-level singleton
_ontology = _Ontology()


def get_ontology() -> _Ontology:
    """Return the module-level ontology singleton."""
    return _ontology
