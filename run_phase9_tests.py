"""
Phase 9 Test Runner — Bypasses Python 3.14 compatibility issues.

Runs all Phase 9 tests using the same app.logic stub approach.
No Hypothesis dependency (incompatible with Python 3.14).
Uses pytest.mark.parametrize for exhaustive testing instead.
"""

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


def run_tests():
    """Run all Phase 9 tests."""
    start = time.monotonic()
    passed = 0
    failed = 0
    skipped = 0
    errors = []

    print("=" * 70)
    print("Phase 9 — Sovereign ML Stack Integration Tests")
    print("=" * 70)

    # Import test modules
    test_modules = []

    # Unit tests
    try:
        from tests.unit import test_phase9_validation

        test_modules.append(("P9.7 Validation", test_phase9_validation))
    except Exception as e:
        errors.append(f"Import error (test_phase9_validation): {e}")
        traceback.print_exc()

    # Property tests (now parametrized, no Hypothesis)
    try:
        from tests.properties import test_ai_output_schemas

        test_modules.append(("P9.3 AI Output Schemas", test_ai_output_schemas))
    except Exception as e:
        errors.append(f"Import error (test_ai_output_schemas): {e}")
        traceback.print_exc()

    try:
        from tests.properties import test_dual_mode_invariants

        test_modules.append(("P9.3 Dual Mode Invariants", test_dual_mode_invariants))
    except Exception as e:
        errors.append(f"Import error (test_dual_mode_invariants): {e}")
        traceback.print_exc()

    try:
        from tests.properties import test_decimal_enforcement

        test_modules.append(("P9.3 Decimal Enforcement", test_decimal_enforcement))
    except Exception as e:
        errors.append(f"Import error (test_decimal_enforcement): {e}")
        traceback.print_exc()

    for module_name, module in test_modules:
        print(f"\n── {module_name} ──")

        # Find test functions and classes
        test_items = []
        for name in sorted(dir(module)):
            obj = getattr(module, name)
            if name.startswith("test_") and callable(obj):
                test_items.append((name, obj, None))
            elif name.startswith("Test") and isinstance(obj, type):
                # Test class — collect methods
                instance = obj()
                for method_name in sorted(dir(instance)):
                    if method_name.startswith("test_"):
                        method = getattr(instance, method_name)
                        test_items.append((f"{name}.{method_name}", method, instance))

        for test_name, test_func, instance in test_items:
            try:
                # Handle parametrized tests: check for pytest.mark.parametrize
                markers = getattr(test_func, "pytestmark", [])
                param_markers = [m for m in markers if m.name == "parametrize"]

                if param_markers:
                    # Run parametrized test with all parameter combos
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

    # ── Summary ─────────────────────────────────────────────────────────────
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


def _expand_parametrize(markers):
    """Expand pytest.mark.parametrize markers into parameter dicts."""
    import itertools

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

    # Cartesian product of all axes
    result = []
    for combo in itertools.product(*all_axes):
        merged = {}
        for d in combo:
            merged.update(d)
        result.append(merged)
    return result


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
