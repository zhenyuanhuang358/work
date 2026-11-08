#!/usr/bin/env python3
"""SKILLS.md 必须与 .claude/skills、.claude/agents 的 frontmatter 同步（2026-11-08 搬家：别的 harness 靠它找 skill）。
运行：python3 -m unittest tests/test_skill_index.py
"""
import glob
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import skill_index as si  # noqa: E402


class SkillIndex(unittest.TestCase):
    def test_committed_index_is_fresh(self):
        self.assertEqual(open(si.OUT, encoding="utf-8").read(), si.build(), "SKILLS.md 过期：python3 tools/skill_index.py")

    def test_every_skill_and_agent_listed(self):
        txt = si.build()
        for p in glob.glob(os.path.join(REPO, ".claude/skills/*/SKILL.md")) + glob.glob(os.path.join(REPO, ".claude/agents/*.md")):
            self.assertIn(os.path.relpath(p, REPO), txt)


if __name__ == "__main__":
    unittest.main()
