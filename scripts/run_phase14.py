"""
Phase 14 — Standalone runner script.

Bypasses circular imports in ``jobs/__init__.py`` by pre-registering
package stubs before any imports.

Usage:
    python scripts/run_phase14.py                # Full run (200 seeds)
    python scripts/run_phase14.py --quick        # Quick run (10 seeds)
    python scripts/run_phase14.py --calibration-only  # Calibration only
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Pre-register package stubs to prevent circular imports through
# jobs/__init__.py -> services -> jobs.simulate_strategy -> circular
_jobs_stub = type(sys)("jobs")
_jobs_stub.__path__ = [os.path.join(_PROJECT_ROOT, "jobs")]
_jobs_stub.__package__ = "jobs"
sys.modules.setdefault("jobs", _jobs_stub)

_rv_stub = type(sys)("jobs.robust_validation")
_rv_stub.__path__ = [os.path.join(_PROJECT_ROOT, "jobs", "robust_validation")]
_rv_stub.__package__ = "jobs.robust_validation"
sys.modules.setdefault("jobs.robust_validation", _rv_stub)

_val_stub = type(sys)("jobs.validation")
_val_stub.__path__ = [os.path.join(_PROJECT_ROOT, "jobs", "validation")]
_val_stub.__package__ = "jobs.validation"
sys.modules.setdefault("jobs.validation", _val_stub)

# Load simulation module via importlib.util (avoids jobs/__init__.py chain)
if "jobs.validation.simulation" not in sys.modules:
    _sim_spec = importlib.util.spec_from_file_location(
        "jobs.validation.simulation",
        os.path.join(_PROJECT_ROOT, "jobs", "validation", "simulation.py"),
    )
    _sim_mod = importlib.util.module_from_spec(_sim_spec)
    sys.modules["jobs.validation.simulation"] = _sim_mod
    _sim_spec.loader.exec_module(_sim_mod)


def _load_mod(name: str, path: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load each robust_validation submodule explicitly
_rv_base = os.path.join(_PROJECT_ROOT, "jobs", "robust_validation")
_load_mod("jobs.robust_validation.config", os.path.join(_rv_base, "config.py"))
_load_mod("jobs.robust_validation.datasets", os.path.join(_rv_base, "datasets.py"))
_load_mod("jobs.robust_validation.evaluator", os.path.join(_rv_base, "evaluator.py"))
_load_mod("jobs.robust_validation.sweeps", os.path.join(_rv_base, "sweeps.py"))
_load_mod("jobs.robust_validation.safety", os.path.join(_rv_base, "safety.py"))
_load_mod("jobs.robust_validation.reports", os.path.join(_rv_base, "reports.py"))
_main_mod = _load_mod("jobs.robust_validation.__main__", os.path.join(_rv_base, "__main__.py"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 14 Final Validation Loop")
    parser.add_argument("--quick", action="store_true", help="Quick run with 10 seeds")
    parser.add_argument(
        "--calibration-only", action="store_true", help="Calibration tier only"
    )
    args = parser.parse_args()
    result = _main_mod.main(quick=args.quick, calibration_only=args.calibration_only)
    sys.exit(0 if result.decision == "FREEZE APPROVED" else 1)
