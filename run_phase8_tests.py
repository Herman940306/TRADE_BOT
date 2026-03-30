"""
Phase 8 Test Runner — Direct Execution
Bypasses pytest and app.logic.__init__.py to run tests directly.

Usage:
    python run_phase8_tests.py
"""

import asyncio
import inspect
import pathlib
import sys
import time
import traceback
import types

# Stub app.logic to bypass __init__.py (which imports prometheus_client
# and other heavyweight modules that hang on Python 3.14)
import app  # noqa: F401

_logic_dir = pathlib.Path(__file__).resolve().parent / "app" / "logic"
stub = types.ModuleType("app.logic")
stub.__path__ = [str(_logic_dir)]
stub.__package__ = "app.logic"
sys.modules["app.logic"] = stub


def run_tests_from_module(module, results):
    """Run all test classes/methods from a module. Handles async tests."""
    for name in sorted(dir(module)):
        obj = getattr(module, name)
        if not isinstance(obj, type) or not name.startswith("Test"):
            continue

        instance = obj()
        for method_name in sorted(dir(instance)):
            if not method_name.startswith("test_"):
                continue
            method = getattr(instance, method_name)
            test_id = f"{name}::{method_name}"

            try:
                if inspect.iscoroutinefunction(method):
                    asyncio.run(method())
                else:
                    method()
                results["passed"].append(test_id)
                print(f"  PASS  {test_id}")
            except AssertionError as e:
                results["failed"].append((test_id, str(e)))
                print(f"  FAIL  {test_id}: {e}")
            except Exception as e:
                results["errors"].append((test_id, str(e)))
                print(f"  ERROR {test_id}: {e}")
                traceback.print_exc()


def main():
    start = time.monotonic()
    results = {"passed": [], "failed": [], "errors": []}

    # Import Phase 8 test modules
    from tests.unit import test_dual_mode_reasoner, test_escalation_policy

    print("=" * 70)
    print("Phase 8 — Escalation Policy Tests")
    print("=" * 70)
    run_tests_from_module(test_escalation_policy, results)

    print()
    print("=" * 70)
    print("Phase 8 — Dual Mode Reasoner Tests")
    print("=" * 70)
    run_tests_from_module(test_dual_mode_reasoner, results)

    elapsed = time.monotonic() - start
    print()
    print("=" * 70)
    total = len(results["passed"]) + len(results["failed"]) + len(results["errors"])
    print(
        f"RESULTS: {total} tests | "
        f"{len(results['passed'])} passed | "
        f"{len(results['failed'])} failed | "
        f"{len(results['errors'])} errors | "
        f"{elapsed:.2f}s"
    )

    if results["failed"]:
        print("\nFAILED TESTS:")
        for tid, msg in results["failed"]:
            print(f"  - {tid}: {msg}")

    if results["errors"]:
        print("\nERROR TESTS:")
        for tid, msg in results["errors"]:
            print(f"  - {tid}: {msg}")

    print("=" * 70)

    return 0 if not results["failed"] and not results["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
