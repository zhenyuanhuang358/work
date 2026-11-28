#!/usr/bin/env python3

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
import sys
sys.path.insert(0, TOOLS)

import options_state as state  # noqa: E402
import deliver_scan  # noqa: E402


class AtomicState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "manifest.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_atomic_write_is_valid_json(self):
        state.atomic_write_json(self.path, {"ok": True, "value": "中文"})
        with open(self.path, encoding="utf-8") as file:
            self.assertEqual(json.load(file)["value"], "中文")
        self.assertFalse([name for name in os.listdir(self.tmp.name) if name.startswith(".tmp-options-")])

    def test_create_is_idempotent_twenty_times(self):
        for _ in range(20):
            manifest = state.create_or_load_manifest(
                self.path, "run-001", asof="2026-11-28T00:00:00+00:00", trigger="scan-run-001"
            )
        self.assertEqual(manifest["run_id"], "run-001")
        self.assertEqual(len(manifest["history"]), 1)

    def test_trigger_conflict_is_rejected(self):
        state.create_or_load_manifest(self.path, "run-001", asof="2026-11-28T00:00:00+00:00", trigger="scan-a")
        with self.assertRaisesRegex(ValueError, "批次冲突"):
            state.create_or_load_manifest(self.path, "run-001", asof="2026-11-28T00:00:00+00:00", trigger="scan-b")

    def test_fetch_reservation_is_stable_twenty_times(self):
        fetch_path = os.path.join(self.tmp.name, "fetch.json")
        for _ in range(20):
            receipt = state.reserve_fetch(fetch_path, "2026-11-28_001")
        self.assertEqual(receipt["trigger"], "scan-2026-11-28_001")
        self.assertEqual(receipt["status"], "RESERVED")

    def test_fetch_completion_rejects_other_batch(self):
        fetch_path = os.path.join(self.tmp.name, "fetch.json")
        receipt = state.reserve_fetch(fetch_path, "run-001")
        with self.assertRaisesRegex(ValueError, "取数批次冲突"):
            state.complete_fetch(fetch_path, trigger="scan-other", commit="abc")
        completed = state.complete_fetch(fetch_path, trigger=receipt["trigger"], commit="abc")
        self.assertEqual(completed["status"], "FETCHED")
        self.assertEqual(completed["remote_commit"], "abc")

    def test_stage_cannot_move_backwards(self):
        state.create_or_load_manifest(self.path, "run-001", asof="2026-11-28T00:00:00+00:00")
        state.transition(self.path, "ANALYZING")
        state.transition(self.path, "DRAFTED")
        with self.assertRaisesRegex(ValueError, "不能倒退"):
            state.transition(self.path, "ANALYZED")

    def test_failed_verify_can_resume_from_draft(self):
        state.create_or_load_manifest(self.path, "run-001", asof="2026-11-28T00:00:00+00:00")
        state.transition(self.path, "ANALYZING")
        state.transition(self.path, "DRAFTED")
        state.transition(self.path, "FAILED_VERIFY", detail="bad report")
        state.transition(self.path, "DRAFTED", detail="edited")
        state.transition(self.path, "VERIFIED")
        self.assertEqual(state.read_json(self.path)["stage"], "VERIFIED")


class PositionGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "positions.json")
        self.now = datetime(2026, 11, 28, 1, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, **values):
        data = {"schema_version": 1, "as_of": self.now.isoformat(), "confirmed": True, "positions": []}
        data.update(values)
        state.atomic_write_json(self.path, data)

    def test_missing_blocks_position_sizing(self):
        self.assertEqual(state.inspect_positions(self.path, now=self.now)["status"], "MISSING")

    def test_unconfirmed_blocks_position_sizing(self):
        self.write(confirmed=False)
        self.assertEqual(state.inspect_positions(self.path, now=self.now)["status"], "UNCONFIRMED")

    def test_stale_blocks_position_sizing(self):
        self.write(as_of=(self.now - timedelta(hours=25)).isoformat())
        self.assertEqual(state.inspect_positions(self.path, now=self.now)["status"], "STALE")

    def test_current_snapshot_passes(self):
        self.write(positions=[{"ticker": "TEST", "contracts": 1}])
        result = state.inspect_positions(self.path, now=self.now)
        self.assertTrue(result["pass"])
        self.assertEqual(result["status"], "CURRENT")


class DeliveryGate(unittest.TestCase):
    def test_verification_alone_is_not_actionable(self):
        scan = {"gates": {name: {"pass": name != "position"} for name in ("data", "market", "position")}}
        self.assertEqual(state.final_delivery_state(scan, True), ("VERIFIED_WITH_BLOCKS", False))

    def test_all_gates_are_required(self):
        scan = {"gates": {name: {"pass": True} for name in ("data", "market", "position")}}
        self.assertEqual(state.final_delivery_state(scan, True), ("READY_FOR_BROKER_CHECK", True))


class DeliveryReceipt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.manifest = os.path.join(self.tmp.name, "run.manifest.json")
        self.scan = os.path.join(self.tmp.name, "run.json")
        self.report = os.path.join(self.tmp.name, "run.report.md")
        self.verification = self.report + ".receipt.json"
        self.delivery = self.report + ".delivery.json"
        state.create_or_load_manifest(self.manifest, "run-001", asof="2026-11-28T00:00:00+00:00")
        state.transition(self.manifest, "ANALYZING")
        state.transition(self.manifest, "DRAFTED")
        with open(self.report, "w", encoding="utf-8") as file:
            file.write("结论：不开新仓\n")
        report_sha = state.sha256_file(self.report)
        state.atomic_write_json(self.scan, {
            "run_id": "run-001",
            "delivery_status": "VERIFIED_WITH_BLOCKS",
            "actionable": False,
            "gates": {"market": {"pass": False, "status": "BLOCK", "reason": "休市"}},
            "verification": {"report_sha256": report_sha, "pass": True},
        })
        state.atomic_write_json(self.verification, {
            "run_id": "run-001",
            "report_sha256": report_sha,
            "verification_passed": True,
            "delivery_status": "VERIFIED_WITH_BLOCKS",
        })
        state.transition(self.manifest, "VERIFIED")

    def tearDown(self):
        self.tmp.cleanup()

    def test_delivery_is_idempotent_and_reaches_delivered(self):
        first = deliver_scan.deliver(self.manifest, self.scan, self.report, self.verification, self.delivery)
        second = deliver_scan.deliver(self.manifest, self.scan, self.report, self.verification, self.delivery)
        self.assertEqual(first, second)
        manifest = state.read_json(self.manifest)
        self.assertEqual(manifest["stage"], "DELIVERED")
        self.assertEqual([row["stage"] for row in manifest["history"]].count("DELIVERED"), 1)

    def test_changed_report_is_rejected(self):
        with open(self.report, "a", encoding="utf-8") as file:
            file.write("changed\n")
        with self.assertRaisesRegex(ValueError, "验证哈希不一致"):
            deliver_scan.deliver(self.manifest, self.scan, self.report, self.verification, self.delivery)


if __name__ == "__main__":
    unittest.main()
