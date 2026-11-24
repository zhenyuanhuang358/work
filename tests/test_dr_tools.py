"""Decision Mode 工具回归：跨文件一致性（dr_consistency）+ 状态机门（dr_state）。"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import dr_consistency  # noqa: E402
import dr_state  # noqa: E402


class Consistency(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.task = "t1"
        self.d = os.path.join(self.tmp, self.task)
        os.makedirs(self.d)
        json.dump({"facts": [{"id": "F1", "desc": "门店", "canonical": ["40–90 家"],
                              "must_in": ["report", "conflicts"], "stale": ["30–99 家"]}]},
                  open(os.path.join(self.d, "facts.json"), "w", encoding="utf-8"), ensure_ascii=False)
        self.old = dr_consistency.ROOT
        dr_consistency.ROOT = self.tmp

    def tearDown(self):
        dr_consistency.ROOT = self.old

    def _write(self, text):
        open(os.path.join(self.d, "report.html"), "w", encoding="utf-8").write(text)
        open(os.path.join(self.d, "conflicts.json"), "w", encoding="utf-8").write(text)

    def test_pass_when_canonical_present(self):
        self._write("2027 门店 40–90 家")
        self.assertEqual(dr_consistency.check(self.task), [])

    def test_fail_when_stale_present(self):
        self._write("旧口径 30–99 家")
        issues = dr_consistency.check(self.task)
        self.assertTrue(any("残留旧口径" in x for x in issues))

    def test_fail_when_missing_canonical(self):
        self._write("其他文字")
        self.assertTrue(dr_consistency.check(self.task))


class StateGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.task = "t2"
        self.d = os.path.join(self.tmp, self.task)
        os.makedirs(self.d)
        self.old = dr_state.ROOT
        dr_state.ROOT = self.tmp

    def tearDown(self):
        dr_state.ROOT = self.old

    def test_frame_requires_falsifier(self):
        json.dump({"decision": "d", "hypotheses": [{"id": "H1", "statement": "s", "falsifier": "", "evidence_needed": ["x"], "core": True}]},
                  open(os.path.join(self.d, "hypotheses.json"), "w", encoding="utf-8"), ensure_ascii=False)
        json.dump({"task": self.task, "decision": "", "decision_confirmed": False, "phase": "frame", "loops": {}, "budget": {}, "gates": {}},
                  open(os.path.join(self.d, "state.json"), "w", encoding="utf-8"))
        rc = dr_state.gate(self.task, "frame", confirm=True)
        self.assertEqual(rc, 1)

    def test_frame_passes_with_complete_hypotheses(self):
        json.dump({"decision": "d", "hypotheses": [{"id": "H1", "statement": "s", "falsifier": "f", "evidence_needed": ["x"], "core": True}]},
                  open(os.path.join(self.d, "hypotheses.json"), "w", encoding="utf-8"), ensure_ascii=False)
        json.dump({"task": self.task, "decision": "", "decision_confirmed": False, "phase": "frame", "loops": {}, "budget": {}, "gates": {}},
                  open(os.path.join(self.d, "state.json"), "w", encoding="utf-8"))
        self.assertEqual(dr_state.gate(self.task, "frame", confirm=True), 0)


if __name__ == "__main__":
    unittest.main()
