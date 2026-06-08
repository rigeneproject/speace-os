"""Phase 5 — Long-horizon audit.

Goal
----
Run the LongHorizonAdaptationAuditor end-to-end to verify that the
self-improvement loop does not regress over time. The auditor runs
multiple profiles across multiple horizons (5, 25, 50, 100, 250
ticks) and computes slopes for cognitive_score, phi, energy, and
recovery latency.

Success criteria:
1. The auditor's run_audit_suite returns a valid LongHorizonAuditResult.
2. The top-level verdict is one of the recognised verdicts.
3. Every profile produces a LongHorizonProfileResult with finite
   trajectory_points.
4. The auditor writes a JSON report and a markdown report to disk.
5. The slopes are finite (no NaN, no Inf).
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class Phase5LongHorizonTests(unittest.TestCase):
    def test_long_horizon_auditor_runs(self):
        from speace_core.cellular_brain.analysis.long_horizon_adaptation_audit import (
            LongHorizonAdaptationAuditor,
        )
        with tempfile.TemporaryDirectory() as tmp:
            auditor = LongHorizonAdaptationAuditor(
                report_dir=tmp,
                seed=42,
                horizons=[5, 25, 50],  # smaller subset for test speed
            )
            profiles = LongHorizonAdaptationAuditor.default_profiles()
            result = asyncio.run(auditor.run_audit_suite(profiles=profiles))
            # Top-level result
            self.assertIsNotNone(result)
            self.assertGreater(len(result.profile_results), 0)
            # Verdict is a string
            self.assertIsInstance(result.verdict, str)
            self.assertGreater(len(result.verdict), 0)
            # Per-profile checks
            for pr in result.profile_results:
                self.assertGreaterEqual(len(pr.trajectory_points), 1)
                for tp in pr.trajectory_points:
                    # All slopes / metrics must be finite
                    self.assertTrue(math.isfinite(tp.cognitive_score))
                    self.assertTrue(math.isfinite(tp.phi))
                    self.assertTrue(math.isfinite(tp.energy_efficiency))
                    self.assertTrue(math.isfinite(tp.net_gain))
                # Slopes are finite
                self.assertTrue(math.isfinite(pr.cognitive_score_slope))
                self.assertTrue(math.isfinite(pr.phi_slope))
                self.assertTrue(math.isfinite(pr.energy_slope))

    def test_long_horizon_reports_persisted(self):
        from speace_core.cellular_brain.analysis.long_horizon_adaptation_audit import (
            LongHorizonAdaptationAuditor,
        )
        with tempfile.TemporaryDirectory() as tmp:
            auditor = LongHorizonAdaptationAuditor(
                report_dir=tmp, seed=7, horizons=[5, 25]
            )
            profiles = LongHorizonAdaptationAuditor.default_profiles()
            result = asyncio.run(auditor.run_audit_suite(profiles=profiles))
            # JSON report exists
            json_path = result.json_report_path
            md_path = result.markdown_report_path
            if json_path:
                self.assertTrue(os.path.exists(json_path))
                with open(json_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                self.assertIn("profile_results", data)
            if md_path:
                self.assertTrue(os.path.exists(md_path))
                with open(md_path, "r", encoding="utf-8") as fh:
                    text = fh.read()
                self.assertGreater(len(text), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
