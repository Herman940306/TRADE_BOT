"""
Phase 10 Test Runner — Bypasses Python 3.14 compatibility issues.

Runs all Phase 10 Alpha Detection Layer tests using the same
app.logic stub approach. No Hypothesis dependency.
"""

import itertools
import os
import sys
import time
import traceback
import types

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Stub app.logic to bypass __init__.py (prometheus_client hang on 3.14)
stub = types.ModuleType("app.logic")
stub.__path__ = [os.path.join(project_root, "app", "logic")]
stub.__package__ = "app.logic"
sys.modules["app.logic"] = stub

# Import pytest skip exception for handling
from _pytest.outcomes import Skipped as PytestSkipped


def _expand_parametrize(markers):
    """Expand pytest.mark.parametrize markers into parameter dicts."""
    all_axes = []
    for marker in markers:
        args = marker.args
        argnames = args[0]
        argvalues = args[1]

        if isinstance(argnames, str):
            names = [n.strip() for n in argnames.split(",")]
        else:
            names = list(argnames)

        axis_params = []
        for val in argvalues:
            if len(names) == 1:
                axis_params.append({names[0]: val})
            else:
                axis_params.append(dict(zip(names, val)))
        all_axes.append(axis_params)

    result = []
    for combo in itertools.product(*all_axes):
        merged = {}
        for d in combo:
            merged.update(d)
        result.append(merged)
    return result


def run_tests():
    """Run all Phase 10 tests."""
    start = time.monotonic()
    passed = 0
    failed = 0
    skipped = 0
    errors = []

    print("=" * 70)
    print("Phase 10 — Alpha Detection Layer Tests")
    print("=" * 70)

    test_modules = []

    # Unit tests
    try:
        from tests.unit import test_phase10_alpha_detection

        test_modules.append(
            ("P10 Unit — Alpha Detection", test_phase10_alpha_detection)
        )
    except Exception as e:
        errors.append(f"Import error (test_phase10_alpha_detection): {e}")
        traceback.print_exc()

    # Property / invariant tests
    try:
        from tests.properties import test_alpha_invariants

        test_modules.append(("P10 Props — Alpha Invariants", test_alpha_invariants))
    except Exception as e:
        errors.append(f"Import error (test_alpha_invariants): {e}")
        traceback.print_exc()

    for module_name, module in test_modules:
        print(f"\n── {module_name} ──")

        test_items = []
        for name in sorted(dir(module)):
            obj = getattr(module, name)
            if name.startswith("test_") and callable(obj):
                test_items.append((name, obj, None))
            elif name.startswith("Test") and isinstance(obj, type):
                instance = obj()
                for method_name in sorted(dir(instance)):
                    if method_name.startswith("test_"):
                        method = getattr(instance, method_name)
                        test_items.append((f"{name}.{method_name}", method, instance))

        for test_name, test_func, instance in test_items:
            try:
                markers = getattr(test_func, "pytestmark", [])
                param_markers = [m for m in markers if m.name == "parametrize"]

                if param_markers:
                    param_sets = _expand_parametrize(param_markers)
                    param_passed = 0
                    param_skipped = 0
                    for i, params in enumerate(param_sets):
                        try:
                            test_func(**params)
                            param_passed += 1
                            passed += 1
                        except PytestSkipped:
                            param_skipped += 1
                            skipped += 1
                        except Exception as e:
                            failed += 1
                            errors.append(f"{module_name}::{test_name}[{i}]: {e}")
                    status = f"{param_passed} passed"
                    if param_skipped:
                        status += f", {param_skipped} skipped"
                    print(f"  PASS: {test_name} ({status})")
                else:
                    result = test_func()
                    if hasattr(result, "__await__"):
                        import asyncio

                        asyncio.run(result)
                    passed += 1
                    print(f"  PASS: {test_name}")
            except PytestSkipped as e:
                skipped += 1
                print(f"  SKIP: {test_name} — {e}")
            except Exception as e:
                failed += 1
                errors.append(f"{module_name}::{test_name}: {e}")
                print(f"  FAIL: {test_name} — {e}")

    elapsed = time.monotonic() - start

    print("\n" + "=" * 70)
    print(
        f"Results: {passed} passed, {failed} failed, {skipped} skipped in {elapsed:.2f}s"
    )
    print("=" * 70)

    if errors:
        print("\nFailures:")
        for err in errors:
            print(f"  ✗ {err}")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
