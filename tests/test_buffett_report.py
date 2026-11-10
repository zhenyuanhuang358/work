#!/usr/bin/env python3
"""巴菲特报告通用模板回归（2026-11-10）。样例 = 英伟达冻结输入 + 叙述（tests/fixtures/buffett）。
钉住的是 KO / NVDA 八轮 Critic 里反复出现的机械错误。运行：python3 -m unittest tests/test_buffett_report.py
"""
import json
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX = os.path.join(REPO, "tests", "fixtures", "buffett")
sys.path.insert(0, os.path.join(REPO, "tools"))
import buffett_report as br  # noqa: E402


def load(n):
    with open(os.path.join(FX, n), encoding="utf-8") as f:
        return json.load(f)


class Template(unittest.TestCase):
    def setUp(self):
        self.V, self.html = br.build(load("nvda_input.json"), load("nvda_narrative.json"))
        self.text = re.sub(r"<[^>]+>", " ", self.html)

    def test_matches_critic_verified_numbers(self):
        """与四轮 Critic 核过的英伟达结果一致：135.27–148.38、−38.0%、74 分。"""
        self.assertEqual([round(x, 2) for x in self.V["iv_range"]], [135.27, 148.38])
        self.assertEqual(self.V["scorecard"]["total"], 74)
        for s in ("135.27", "148.38", "-38.0%", "81.16", "74 / 100"):
            self.assertIn(s, self.text)

    def test_moat_sensitivity_rescored_not_copied(self):
        """NVDA R3：9 分敏感性行抄了主底稿评分（4A 仍为 0，总分 81）。模板必须重跑：89，且注明观察、非买入。"""
        self.assertRegex(self.text, r"9 分\s+25%\s+282\.89–327\.16\s+34\.0%\s+89（强力买入区域）\s+安全边际低于门槛：观察、非买入")

    def test_captions_follow_moat_band(self):
        """NVDA R3：护城河改 6 分后，脚本里还写着 8% 终端上限。图注与依据栏必须跟着分数走。"""
        self.assertIn("5–6 = 中等：阶段 1 增速上限 12%，终端增长上限 5%", self.text)
        self.assertIn("上限 5% × 60% / × 80%", self.text)
        self.assertNotIn("上限 8%", self.text)

    def test_placeholders_filled_and_structure(self):
        self.assertNotRegex(self.html, r"\{(lo|hi|price|mos|buy|hurdle|total|rating|implied|cap|moat)\}")
        for sec in ("一句话结论", "一、护城河分析", "四、内在价值估算", "五、巴菲特评分卡", "七、数据盲区与敏感性", "来源索引", "分析师附注", "未核实项"):
            self.assertIn(sec, self.text)
        self.assertIn('data-valuation="memory/state/valuations/nvda_2026-11-09.json"', self.html)


if __name__ == "__main__":
    unittest.main()
