#!/usr/bin/env python3
"""期权扫描回归测试：用 2026-11-05 冻结的真实数据（tests/fixtures/options_2026-11-05），把当天修过的每个问题钉住。

为什么（2026-11-06 改造）：11/05 四次扫描修了约 15 处，都没有测试——下次改代码可能悄悄改回去。
每个测试名对应 memory/state/feedback.jsonl 里一条反馈的 test 字段；self_check C11 会核对这些名字真实存在。
运行：python3 -m unittest tests/test_options_regression.py -v      （约 10 秒，不联网、不读 git）
"""
import argparse
import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX = os.path.join(REPO, "tests", "fixtures", "options_2026-11-05")
ASOF = "2026-11-05T17:45:00"
sys.path.insert(0, os.path.join(REPO, "tools"))
import gap_stress as gs  # noqa: E402
import option_quote as oq  # noqa: E402
import tail_light as tl  # noqa: E402


def ns(**kw):
    d = dict(right="P", bp=5470.0, z_min=1.2, max_age=20, dte_max=None, strikes=None, json=False, ticker=None, expiry=None)
    d.update(kw)
    return argparse.Namespace(**d)


class Base(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        os.chdir(FX)
        oq.NOW = datetime.fromisoformat(ASOF).replace(tzinfo=timezone.utc)
        oq._HV_CACHE.clear()
        self.chain = json.load(open("options_chain.json"))

    def tearDown(self):
        os.chdir(self.cwd)
        oq.NOW = None

    def collect(self, chain=None, **kw):
        with contextlib.redirect_stdout(io.StringIO()):
            return oq.collect(ns(**kw), chain or self.chain)


class OptionQuote(Base):
    def test_hv_missing_is_flagged_not_silent(self):
        """11/05：49/60 只无 HV，IV/HV 过滤静默失效、照样 ✅。无 HV 必须标 ⚠无HV，且不得过关。"""
        ch = copy.deepcopy(self.chain)
        ch["tickers"]["TLT"].pop("hv30", None)
        oq._HV_CACHE["TLT"] = None
        r = self.collect(ch, dte_max=29)
        self.assertFalse([x for x in r["ok"] if x["ticker"] == "TLT"], "TLT 无 HV 仍过关")
        self.assertIn("⚠无HV", r["reasons_by_ticker"])

    def test_fixture_has_hv_for_all_watch(self):
        """fetch_options 用 yfinance 算 hv30 后，60 只应全部有 HV。"""
        w = json.load(open("options_watch.json"))["tickers"]
        self.assertEqual([t for t in w if not self.chain["tickers"].get(t, {}).get("hv30")], [])

    def test_term_premium_gate_blocks_30_45(self):
        """11/05：期限溢价 < 1.20 时 30–45 天档仍打 ✅。现在必须 ⛔期限溢价，且没有 ≥30 天的过关行。"""
        r = self.collect(dte_max=None)
        today = oq.NOW.date()
        long_ok = [x for x in r["ok"] if (datetime.fromisoformat(x["expiry"]).date() - today).days >= 30]
        self.assertEqual(long_ok, [])
        self.assertGreater(r["term_gate_tickers"], 0)

    def test_main_cause_not_hijacked_by_term_gate(self):
        """11/05：47 只主因显示期限溢价，盖住 20–29 天真实原因（XLE 实为报价差 / z 不够）。"""
        r = self.collect(dte_max=None)
        self.assertNotIn("⛔期限溢价", set(r["main_cause"].values()))
        self.assertIn(r["main_cause"]["XLE"], {"⛔报价差", "⛔IV不贵", "z不够", "⚠链不够宽"})

    def test_rate_sensitive_hood_sofi(self):
        """11/05：HOOD 22 个过关行靠手工否决。持有期含 CPI 11/10 → ⛔利率敏感。"""
        for side in ("P", "C"):
            r = self.collect(right=side, dte_max=29)
            self.assertFalse([x for x in r["ok"] if x["ticker"] in ("HOOD", "SOFI")])
            self.assertEqual(r["main_cause"]["HOOD"], "⛔利率敏感")

    def test_stale_quotes_are_visible(self):
        """11/06 试跑：报价过期时汇总显示「0 行、主因空」。必须标 ⛔报价过期。"""
        oq.NOW = datetime(2026, 11, 6, 5, 0, tzinfo=timezone.utc)
        r = self.collect(dte_max=29)
        self.assertEqual(r["ok"], [])
        self.assertEqual(r["reasons_by_ticker"].get("⛔报价过期"), 60)

    def test_margin_gate_uses_cash_not_buying_power(self):
        """profile 1.1zc：保证金 ×1.15 > 可取现金 → ⛔保证金。bp 很小时不得有过关行。"""
        r = self.collect(bp=300.0, dte_max=29)
        self.assertEqual(r["ok"], [])
        self.assertIn("⛔保证金", r["reasons_by_ticker"])

    def test_golden_pass_rows(self):
        """当天真实结论：P 只有 TLT 79P 11/27 过关（金样例；规则改了这里要同步改并写进 feedback）。"""
        r = self.collect(dte_max=29)
        self.assertEqual([(x["ticker"], x["expiry"], x["strike"]) for x in r["ok"]], [("TLT", "2026-11-27", 79.0)])
        x = r["ok"][0]
        self.assertTrue(x["spread"] <= 0.10 and x["z"] >= 1.2 and x["margin"] * 1.15 <= 5470)


class GapStress(Base):
    def test_tlt_gap_numbers(self):
        """跳空压力：TLT 低波动，−3% 是 4–5 个日σ 的罕见事件，且一步跳过 2× 止损。"""
        r = self.collect(dte_max=29)
        x = r["ok"][0]
        rows = gs.stress("P", x["spot"], x["strike"], x["t"], x["iv"], x["bid"], x["hv30"], x["move"])
        self.assertEqual([s["scenario"][:3] for s in rows][:2], ["−3%", "−5%"])
        self.assertTrue(4.0 < rows[0]["sigmas"] < 5.5, rows[0]["sigmas"])
        self.assertTrue(all(s["skips_stop"] for s in rows[:2]))
        self.assertGreaterEqual(rows[0]["buyback"], rows[0]["flat"])  # IV×1.3 档不低于 IV 不变档


class TailLight(Base):
    def test_red_with_skew_resident(self):
        """11/05 手算结果：红灯，SKEW 常驻项不计共振，期限溢价 < 1.20 → 30–45 天档关。"""
        r = tl.compute(json.load(open("tail_history.json")), json.load(open("stock_prices.json")))
        self.assertEqual(r["light"], 2)
        self.assertIn("skew", [m for m, _ in r["resident"]])
        self.assertNotIn("skew", r["non_green"])
        self.assertFalse(r["long_band_open"])


class ScanAndVerify(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.out)

    def scan(self):
        subprocess.run([sys.executable, os.path.join(REPO, "tools", "scan.py"), "run", "--bp", "5470", "--asof", ASOF,
                        "--root", FX, "--history", os.path.join(FX, "tail_history.json"), "--out", self.out],
                       check=True, capture_output=True)
        sid = "2026-11-05_1745Z"
        return os.path.join(self.out, sid + ".json"), json.load(open(os.path.join(self.out, sid + ".json")))

    def verify(self, sp, text):
        rp = os.path.join(self.out, "r.md")
        open(rp, "w").write(text)
        with contextlib.redirect_stdout(io.StringIO()):
            import verify_scan
            code = verify_scan.run(rp, sp)
        return code, {c["id"]: c["pass"] for c in json.load(open(sp))["verification"]["checks"]}

    def test_scan_gates(self):
        """11/05：红灯 + 非农前一日 → can_open False，两条理由都要写出。四份产物 trigger 对上。"""
        _, s = self.scan()
        self.assertFalse(s["can_open"])
        self.assertTrue(any("红灯" in w for w in s["why_not"]) and any("Non-Farm" in w for w in s["why_not"]))
        self.assertTrue(s["freshness"]["ok"])

    def test_scan_rows_carry_assign_and_pressure(self):
        """11/06 前后对比：旧主文件要求的 R5 接货额、第 4 条事件压力，新底稿里必须有字段承载。"""
        _, s = self.scan()
        x = s["sides"]["P"]["ok"][0]
        self.assertEqual(x["assign_1"], round(x["strike"] * 100))
        self.assertIn("pressure", x)
        import scan
        self.assertTrue(scan.PRESSURE_RE.search("Acme announces $2 billion secondary offering"))
        self.assertIsNone(scan.PRESSURE_RE.search("Uber Beat on 20% Bookings Growth"))
        # 11/06 回放：TLT 属利率敏感板块，📰 素材必须带上联储讲话；草稿里卖 call 不能写「接货」；同标的多张要提醒第 16 条
        self.assertTrue(all(x.get("fed_channel") for side in "PC" for x in s["sides"][side]["ok"]))
        draft = open(os.path.join(self.out, "2026-11-05_1745Z.draft.md")).read()
        call_blocks = [b for b in draft.split("\n- ") if "C｜收入" in b]
        self.assertTrue(call_blocks and all("接货" not in b for b in call_blocks))
        self.assertIn("第 16 条", draft)

    def test_verify_good_report_passes(self):
        sp, s = self.scan()
        x = s["sides"]["P"]["ok"][0]
        good = (f"结论：今天不开新仓，红灯且明日非农。\n\n## 今日消息面\n- Hammack、Barkin 主张加息 → 利率敏感板块不利\n\n"
                f"## 候选\n- 卖出 TLT {x['strike']:g} put（看跌）\n  代码 TLT {x['expiry']} {x['strike']:g}P｜收入 ${x['income']:.0f}/张\n  止损亏损 1/3/6 张：…\n"
                f"  跳空：…\n  📰 鹰派讲话 → 不利\n\n## 请在平台核实\n- 可取现金\n")
        code, r = self.verify(sp, good)
        self.assertEqual(code, 0, r)

    def test_verify_catches_bad_report(self):
        """防：红灯写开、编造合约、漏 📰、数字对不上、残留占位。"""
        sp, s = self.scan()
        x = s["sides"]["P"]["ok"][0]
        bad = (f"结论：今天开 TLT。\n\n## 今日消息面\n- 【待判断】\n\n## 候选\n"
               f"- TLT {x['expiry']} {x['strike']:g}P｜收入 $99/张\n  跳空：…\n"
               f"- HOOD 2026-11-27 55P｜收入 $49/张\n\n## 请在平台核实\n")
        code, r = self.verify(sp, bad)
        self.assertEqual(code, 1)
        for vid in ("V2", "V4", "V5", "V6", "V7", "V9", "V11"):
            self.assertFalse(r[vid], vid)


class FedSpeakFilter(unittest.TestCase):
    def test_same_surname_obituary_filtered(self):
        """11/05：Google News 把同姓讣告（Williams）匹配成联储讲话。标题须含 Fed / 利率等词。"""
        import re
        pat = re.compile(r"Fed|FOMC|[Rr]ate|[Ii]nflation|[Pp]olicy")
        self.assertIsNone(pat.search("Cheryl 'Sherrie' Anne Williams Okert - The Latrobe Bulletin"))
        self.assertIsNotNone(pat.search("Fed's Hammack favors gradual rate-hike path to lower inflation - Reuters"))
        src = open(os.path.join(REPO, "scripts", "fetch_fed.py")).read()
        self.assertIn("同姓误匹配", src)  # 过滤仍在生产代码里


if __name__ == "__main__":
    unittest.main()
