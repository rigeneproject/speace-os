"""Self-test for prop-ch-001 writers.

Runs ``morphology_writers._self_test()`` and prints PASS/FAIL. Exits 0 on
PASS, 1 on FAIL.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from speace_core.monitoring.morphology_writers import _self_test


def main() -> int:
    result = _self_test()
    print("=" * 60)
    print("SELF-TEST: prop-ch-001 morphology/self_model writers")
    print("=" * 60)
    print(json.dumps(result, indent=2))
    print("=" * 60)

    expected_keys = {
        "morphology_ok",
        "self_model_ok",
        "coherence_phi_present",
        "drift_signal_available",
    }
    ok = all(result.get(k) for k in expected_keys)
    if ok:
        print("PASS: writers are producing both files with non-zero phi and drift signal")
        return 0
    print("FAIL: missing one or more expected behaviours")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
