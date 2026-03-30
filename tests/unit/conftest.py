"""
Project Autonomous Alpha — Test Configuration
Phase 8 Unit Tests conftest.py

PURPOSE
-------
The app.logic.__init__.py imports heavyweight modules (order_manager,
dispatcher, etc.) that transitively import prometheus_client, which
hangs on Python 3.14. This conftest.py pre-registers a stub
app.logic package in sys.modules so that importing Phase 8 modules
(reasoning_mode, escalation_policy, dual_mode_reasoner) bypasses
the __init__.py import chain.

This conftest is loaded BEFORE any test module collection, so the
sys.modules override is in place before test files import from
app.logic.*.
"""

import sys
import types

# Only stub app.logic if it hasn't been loaded yet
if "app.logic" not in sys.modules:
    import app  # noqa: F401 — ensure parent package is registered

    stub = types.ModuleType("app.logic")
    stub.__path__ = [str(types.ModuleType.__module__)]  # type: ignore[attr-defined]
    # Use the actual filesystem path
    import pathlib

    _logic_dir = pathlib.Path(__file__).resolve().parent.parent.parent / "app" / "logic"
    stub.__path__ = [str(_logic_dir)]
    stub.__package__ = "app.logic"
    sys.modules["app.logic"] = stub
