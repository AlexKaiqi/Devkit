"""
Testing helper module — utilities for working with testing strategies
from testing-methodology.yaml via the ontology layer.
"""

from __future__ import annotations

import logging
from typing import Optional

from methodology.ontology import get_ontology

log = logging.getLogger("methodology-testing")


def get_testing_strategy_for_change_type(change_type_str: str) -> Optional[dict]:
    """
    Return the testing strategy dict for a given ChangeType string.
    Returns None if not found.
    """
    ontology = get_ontology()
    return ontology.get_testing_strategy(change_type_str)


def get_required_approaches(change_type_str: str) -> list[str]:
    """
    Return the list of required testing approaches for a ChangeType.
    Returns empty list if strategy not found.
    """
    strategy = get_testing_strategy_for_change_type(change_type_str)
    if not strategy:
        return []
    return strategy.get("required_approaches", [])


def get_ordered_steps(change_type_str: str) -> list[dict]:
    """
    Return the ordered testing steps for a ChangeType.
    Returns empty list if strategy not found.
    """
    strategy = get_testing_strategy_for_change_type(change_type_str)
    if not strategy:
        return []
    return strategy.get("ordered_steps", [])


def get_coverage_mandate(change_type_str: str) -> dict:
    """
    Return the coverage mandate for a ChangeType.
    Returns {"min_percent": 0} if strategy not found.
    """
    strategy = get_testing_strategy_for_change_type(change_type_str)
    if not strategy:
        return {"min_percent": 0}
    return strategy.get("coverage_mandate", {"min_percent": 0})


def list_testing_approaches() -> list[str]:
    """Return all defined testing approach instances."""
    ontology = get_ontology()
    return ontology.list_testing_approaches()


def has_hard_block_steps(change_type_str: str) -> bool:
    """
    Return True if any ordered step in the strategy has is_hard_block=True.
    """
    steps = get_ordered_steps(change_type_str)
    return any(s.get("is_hard_block", False) for s in steps)
