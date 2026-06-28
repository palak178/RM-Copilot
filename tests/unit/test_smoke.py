"""Smoke test — proves the scaffold is healthy (milestone M0).

Verifies that the package and its layered subpackages import cleanly and that
packaging/version metadata is present. No business logic is exercised here:
domain, data, services, tools, agent, and UI are implemented in later milestones.
"""

from __future__ import annotations

import importlib

import rm_copilot

LAYERS = [
    "rm_copilot.domain",
    "rm_copilot.data",
    "rm_copilot.services",
    "rm_copilot.tools",
    "rm_copilot.agent",
    "rm_copilot.observability",
    "rm_copilot.config",
]


def test_package_version_is_a_nonempty_string() -> None:
    assert isinstance(rm_copilot.__version__, str)
    assert rm_copilot.__version__


def test_all_layers_import() -> None:
    """Every architectural layer (CLAUDE.md) imports without side effects."""
    for layer in LAYERS:
        module = importlib.import_module(layer)
        assert module is not None
