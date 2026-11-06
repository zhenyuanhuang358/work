#!/usr/bin/env python3
"""报告检查回归（2026-11-06 期权线方法推广到报告线）。样例 = 已交付报告的冻结副本（tests/fixtures/reports，原件不动）。
每条测试钉住一个真实发现：误报（合规声明被当违规、表头「#」被当 Markdown）和真违规写法必须被抓。
运行：python3 -m unittest tests/test_report_check.py -v
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX = os.path.join(REPO, "tests", "fixtures", "reports")
sys.path.insert(0, os.path.join(REPO, "tools"))
import report_check as rc  # noqa: E402


def ids(r, failed=True):
    return {c["id"] for c in r["checks"] if (not c["pass"]) == failed}


def synth(body, suffix="_Research_Report.html"):
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(f"<html><body>{body}<div>来源：公司年报 https://example.com/a</div><p>结尾</p><p>分析师附注 Analyst's Note</p></body></html>")
    f.close()
    return f.name


class Compliance(unittest.TestCase):
    """用户 11/06：数据来源与合规最不能错。"""

    def test_true_violations_caught(self):
        for bad in ["<p>海底捞华南区 2025 年翻台率 4.2 次，来自内部报表。</p>",
                    "<p>海底捞不对外公布的内部数据显示，华南人效 12 万。</p>",
                    "<p>据我任职期间了解，绿茶门店人效为内部数据 12 万元。</p>"]:
            p = synth(bad)
            self.assertIn("G1", ids(rc.run(p)), bad)
            os.unlink(p)

    def test_compliance_disclaimers_not_flagged(self):
        """11/06 基线：10 份 G1 命中全是合规声明 / 第三方数据，修正后这几份必须不报。"""
        for f in ("catering_2026_greentea_positioning_Research_Report.html", "greentea_ai_spend_survey_2026.html"):
            self.assertNotIn("G1", ids(rc.run(os.path.join(FX, f))), f)

    def test_placeholder_caught(self):
        """11/06 AI 导购报告：裁决区留着「见交付说明（Critic 独立评审后填写）」。"""
        p = synth("<p>评审裁定：见交付说明（Critic 独立评审后填写）。</p>")
        self.assertIn("C5", ids(rc.run(p)))
        os.unlink(p)

    def test_post_negation_disclaimer_not_flagged(self):
        """11/06 AI 导购提纲：开场口径「海底捞、绿茶的内部数据和合作细节我不展开」否定词在后，不能误报；真违规仍要抓。"""
        p = synth("<p>我讲的都是公开信息；海底捞、绿茶的内部数据和合作细节我不展开。</p>")
        self.assertNotIn("G1", ids(rc.run(p)))
        os.unlink(p)
        p = synth("<p>海底捞的内部数据显示，华南人效 12 万，这个我可以展开讲。</p>")
        self.assertIn("G1", ids(rc.run(p)))
        os.unlink(p)

    def test_known_listed_disclaimer_still_flagged_for_human(self):
        """botinkit 的「不应披露」清单否定词在 80 字外：宁可多报交人工，不放宽窗口（合规优先）。"""
        self.assertIn("G1", ids(rc.run(os.path.join(FX, "botinkit_Research_Report.html"))))


class Sources(unittest.TestCase):
    def test_no_source_index_fails(self):
        p = tempfile.NamedTemporaryFile("w", suffix="_Research_Report.html", delete=False, encoding="utf-8")
        p.write("<html><body><p>营收 12 亿元，同比 30%。</p><p>分析师附注</p></body></html>")
        p.close()
        self.assertIn("S1", ids(rc.run(p.name)))
        os.unlink(p.name)

    def test_summary_level_phrases_warned(self):
        p = synth("<p>据搜索，门店数 1,200 家。</p>")
        self.assertIn("S3", ids(rc.run(p)))
        os.unlink(p)

    def test_reference_report_has_no_source_index(self):
        """11/06 发现：Earner 参考样例 00538 没有来源索引（只有「数据质量声明」）——检查必须照实报。"""
        self.assertIn("S1", ids(rc.run(os.path.join(FX, "00538_Copilot_Report.html"))))


class Format(unittest.TestCase):
    def test_table_hash_header_not_markdown(self):
        """11/06 基线：表头单独一格「#」被误报 Markdown（4 份）。"""
        self.assertNotIn("C1", ids(rc.run(os.path.join(FX, "618_2026_ecommerce_Research_Report.html"))))

    def test_real_markdown_caught(self):
        p = synth("<p>## 核心结论</p><p>营收 **12 亿**</p>")
        self.assertIn("C1", ids(rc.run(p)))
        os.unlink(p)

    def test_earner_template_drift_detected(self):
        """11/06 抽查：已交付财报报告没有一份是 14 节；00538 只有 8 组双语标题。"""
        r = rc.run(os.path.join(FX, "00538_Copilot_Report.html"))
        self.assertIn("E1", ids(r))
        self.assertTrue({"E3", "E4", "E5", "E6"} <= ids(r, failed=False))

    def test_earner_full_template_passes_structure(self):
        secs = "".join(f'<section data-sec="{i}"><div class="section-zh">中{i}</div><div class="section-en">EN{i}</div>'
                       f'{"<svg></svg>" if i <= 5 else ""}</section>' for i in range(1, 15))
        body = (secs + "<p>熊市 基准 牛市 目标价</p><div class='verdict'></div>"
                "<style>body{font-family:'IM Fell English','Songti SC';color:#0a0a0b;background:#f1efea}"
                ".c{color:#8b6c42}.g{color:#c9a84c}</style>")
        p = synth(body, suffix="_Copilot_Report.html")
        r = rc.run(p)
        self.assertFalse({"E1", "E2", "E3", "E4", "E5", "E6"} & ids(r), ids(r))
        os.unlink(p)

    def test_c3_requires_each_scenario_price(self):
        """11/06 首次实测：UBER 报告三情景未登记，但 predictions.md 里有一条 UBER 期权旧预测，C3 只查标的名就放行了。"""
        p = synth("<p>熊市 $11 基准 $22 牛市 $33 目标价</p>", suffix="_Copilot_Report.html")
        stem_path = os.path.join(os.path.dirname(p), "uber_" + os.path.basename(p).split("_", 1)[1])
        os.rename(p, stem_path)
        r = rc.run(stem_path)
        c3 = [c for c in r["checks"] if c["id"] == "C3"][0]
        self.assertFalse(c3["pass"], c3)  # 11/22/33 不在任何 UBER 预测行里
        os.unlink(stem_path)

    def test_e7_e8_transcript_quotes(self):
        """11/06 用户：「电话会原话一定要拿到」。美股无引语 → E7；引语被改写 → E8（对照 transcripts/ 原文逐字核对）。"""
        secs = "".join(f'<section data-sec="{i}"></section>' for i in range(1, 15))
        no_q = synth(secs + "<p>熊市 基准 牛市</p>", suffix="_Copilot_Report.html")
        r = rc.run(no_q)
        self.assertIn("E7", ids(r))
        os.unlink(no_q)
        real = "We are very optimistic about the trends as we see them in October and going into Q4."
        for quote, ok in ((real, True), (real.replace("very optimistic", "extremely confident"), False)):
            body = secs + f'<div class="quote">“{quote}”</div><div class="quote">“{quote}”</div>' \
                   '<a href="https://www.fool.com/earnings/call-transcripts/x/">t</a>'
            p = synth(body, suffix="_Copilot_Report.html")
            up = os.path.join(os.path.dirname(p), "uber_" + os.path.basename(p))
            os.rename(p, up)
            e8 = [c for c in rc.run(up)["checks"] if c["id"] == "E8"][0]
            self.assertEqual(e8["pass"], ok, e8)
            os.unlink(up)

    def test_transcript_speaker_parsing_both_formats(self):
        """fetch_transcript：2026 版 Motley Fool 为「Name: 发言」同段（UBER 实测），旧版为「Name -- Title」单独成段。"""
        sys.path.insert(0, os.path.join(REPO, "scripts"))
        import fetch_transcript as ft
        new = open(os.path.join(REPO, "tests", "fixtures", "transcripts", "uber_excerpt.txt")).read()
        self.assertIn("Operator", {t["speaker"] for t in ft.speakers(new)})
        old = "Dara Khosrowshahi -- Chief Executive Officer\nThanks everyone.\nJohn Doe -- Analyst\nA question."
        self.assertEqual([t["speaker"].split("（")[0] for t in ft.speakers(old)], ["Dara Khosrowshahi", "John Doe"])

    def test_uber_reference_sample_full_pass(self):
        """用户 11/06 认可的 Earner 新样例：E1–E8 全过、无 WARN（14 节、来源索引、原话逐字出自原文、三情景已登记）。"""
        r = rc.run(os.path.join(FX, "uber_Copilot_Report.html"), pdf=os.path.join(REPO, "reports", "uber_Copilot_Report.pdf"))
        bad = [c["id"] for c in r["checks"] if not c["pass"] and c["id"] != "C2"]  # C2 依赖本地 PDF（被 .gitignore）
        self.assertEqual(bad, [], r["checks"])

    def test_voices_market_filter(self):
        """fetch_voices 11/06 首跑真实标题：职场八卦 / 人生感悟不进；对华贸易、芯片看跌期权要进。"""
        sys.path.insert(0, os.path.join(REPO, "scripts"))
        import fetch_voices as fv
        noise = ["Billionaires Ray Dalio and Richard Branson hate workplace gossip—and men could pay the price at work",
                 "Ray Dalio: Open-minded people seek growth through questioning and learning"]
        signal = ["Bessent, Greer Raise Concerns on China Trade Deal Actions",
                  "Michael Burry Sold 25% of His Chip Puts and Says He’s Still Very Bearish"]
        self.assertFalse(any(fv.MARKET.search(x) for x in noise))
        self.assertTrue(all(fv.MARKET.search(x) for x in signal))

    def test_research_rules(self):
        """Merlin / restaurant-research：无分析师附注、正文禁用句 → FAIL。"""
        p = tempfile.NamedTemporaryFile("w", suffix="_Research_Report.html", delete=False, encoding="utf-8")
        p.write("<html><body><p>需要说明的是，本题数据有限。</p><div>来源：年报</div></body></html>")
        p.close()
        self.assertTrue({"R1", "R2"} <= ids(rc.run(p.name)))
        os.unlink(p.name)

    def test_good_samples_pass(self):
        """好样例：11/06 基线中无 FAIL 的两份。规则改了导致它们失败，要么规则错，要么写进 feedback 说明。"""
        for f in ("haichang_it_Research_Report.html", "greentea_ai_spend_survey_2026.html", "uber_Copilot_Report.html"):
            self.assertTrue(rc.run(os.path.join(FX, f))["pass"], f)


if __name__ == "__main__":
    unittest.main()
