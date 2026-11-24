"""Merlin M0 输入契约工具回归（2026-11-24）。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools", "merlin_outline.py")


def run(*args):
    return subprocess.run([sys.executable, TOOL, *args], capture_output=True, text=True)


class MerlinOutline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.qfile = os.path.join(self.tmp, "outline.txt")
        open(self.qfile, "w", encoding="utf-8").write("Q1 | 翻台率多少\nQ2 | 利润率多少\n")

    def test_init_then_check_fails_on_placeholders(self):
        r = run("init", "t", "--questions", self.qfile, "--root", self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = run("check", "t", "--root", self.tmp)
        self.assertEqual(r.returncode, 1)
        self.assertIn("缺 真实想问", r.stdout)

    def test_check_passes_after_filling(self):
        run("init", "t", "--questions", self.qfile, "--root", self.tmp)
        p = os.path.join(self.tmp, "t", "outline.json")
        d = json.load(open(p, encoding="utf-8"))
        for q in d["questions"]:
            q.update({"intent": "判断经营质量", "decision": "是否继续开店",
                      "answer_form": "区间+判断", "data_need": "公开财报"})
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        r = run("check", "t", "--root", self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_missing_outline_json_fails(self):
        r = run("check", "nope", "--root", self.tmp)
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
