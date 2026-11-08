# AGENTS.md — 给任何 agent harness 的入口（2026-11-08）

这是一人公司的 agent 系统：期权卖方扫描、财报 / 巴菲特 / 调研报告、筛选器、内容生产。
原来跑在 Claude Code 上；本文件把它依赖的约定写成任何 harness（如接 DeepSeek 的 agent 工具）都能照做的步骤。
**规则正文不在这里**，在下面列的文件里；本文件只说读什么、按什么顺序读，以及 Claude Code 专有功能怎么替代。

## 1. 开场必读（按顺序）

1. `CLAUDE.md`：全部工作规则。文件名带 Claude，但内容与模型无关，**全部适用**：第一性原理、预测登记、报告路由、COO 流水线、Critic 门控、记忆约定。
2. `memory/profile.md`：历史教训与用户偏好。每个会话第一次干活前必读。
3. `memory/state/handoff.md`：当前状态、硬约束、待办，以及已排除、不要再提的路线。
4. `SKILLS.md`：全部 skill 与子代理的索引，由 `tools/skill_index.py` 从 frontmatter 自动生成。

## 2. 硬约束（摘自 handoff §1 与 CLAUDE.md，违反任何一条都比做不完更糟）

- 期权只做卖方单腿（卖 put、卖价外 call），绝不卖价内 call；保证金 ×1.15 ≤ 可取现金，以 `memory/state/options-journal.md` 最新记录为准；不做回本单；不擅自建每日定时扫描。
- 合规：不披露海底捞（6862）、绿茶（6831）的任何未公开数据；不帮客户文章过 AI 检测；简历不编数字。
- 凭证只放 GitHub Secrets，不写进仓库或对话。
- 没有来源的数字不可用；搜索摘要不算来源，要看原文。
- 生成和评审不能在同一个上下文里做（Critic 规则）。

## 3. Skill 怎么用（Claude Code 会自动做，别的 harness 要手动做）

- 用户的话命中 `SKILLS.md` 里的触发词或场景时，读对应的 `.claude/skills/<name>/SKILL.md`（hub）。
- hub 末尾有「Spoke 加载表」，按场景再读 `references/*.md`。spoke 条件加载，不要一次全读。
- CLAUDE.md 的路由优先于触发词：期权、调研、财报、内容四类任务先读 `.claude/skills/coo/SKILL.md`，由它串完整条流水线。

## 4. Claude Code 专有功能 → 替代做法

| 文件里出现的说法 | 含义 | 别的 harness 怎么做 |
|---|---|---|
| 子代理、`.claude/agents/*.md`、「fresh subagent」 | 独立上下文里跑的角色 | 开**新对话**，用该文件正文作系统提示，只给任务需要的文件；Critic 必须这样跑 |
| `SendUserFile` | 把文件推给用户 | 告诉用户文件路径，或用 harness 自带的发送方式 |
| `send_later`、trigger、定时任务 | Claude 云端定时器 | 改用 GitHub Actions 的 `schedule:` 或本机 cron；不得擅自重建每日期权扫描 |
| `WebSearch` / `WebFetch` | 联网 | harness 自带的联网工具；要原文就走 Actions（见 §5） |
| Artifact、PR 订阅 | Claude 网页端功能 | 不需要 |
| `$ARGUMENTS` 等参数替换 | skill 渲染机制 | 忽略；skill 里美元额不写死，就是因为这个 |

## 5. 联网取数：一律走 GitHub Actions

会话环境常常打不开 sec.gov、cboe、fool.com 等站点。做法是：

1. 改触发文件并推送：
   - `pages_request.json`：任意网页 / PDF 原文
   - `financials_request.json`：SEC 10-K 科目
   - `transcript_request.json`：电话会原文
   - `*_trigger.txt`：其他数据
2. 对应 `.github/workflows/*.yml` 自动运行，把产物提交回分支：
   - `pages/`、`financials/`、`transcripts/`
   - `options_chain.json`、`stock_prices.json`、`news.json`、`fed_speak.json`、`macro_actuals.json`、`voices.json`
3. `git fetch && git merge` 后读产物。
4. 期权扫描的统一入口是 `python3 tools/scan.py fetch / run / verify`，四份产物的 trigger 全对上才往下走。

需要的 Secrets：`FINNHUB_TOKEN`、`ANTHROPIC_API_KEY`（jev-bench、nvda-earner-auto 两个工作流用）、`TYPESAFE_API_KEY`。

## 6. 仍直接调用 Anthropic API 的代码（换 DeepSeek 时要改）

- `.github/workflows/jev-bench.yml`、`.github/workflows/nvda-earner-auto.yml`
- `earnings_copilot/`（agent.py、pipeline.py、analysis/analyzer.py、cli.py、extractors/pdf.py、data/consensus.py）、`merlin/`（analyzer.py、research_agents.py）、`test_agent.py`

DeepSeek API 兼容 OpenAI 格式。要换就改用 OpenAI SDK 并设置它的 base_url，密钥加进 Secrets。**尚未改**，改完要跑对应测试。
核心工作流（期权、报告检查、估值、筛选）全是确定性 Python，不调用任何模型 API。

## 7. 验证（改了东西就跑；没有证据不说「通过」）

```
python3 -m unittest tests/test_options_regression.py tests/test_report_check.py tests/test_screen_check.py tests/test_owner_value.py tests/test_skill_index.py
python3 tools/self_check.py --quiet
python3 tools/report_check.py <报告.html> --record     # 交付任何 HTML 报告前
python3 tools/skill_index.py --check                    # 改了任何 SKILL.md / agent 后
```

结果按四类状态汇报：自动验证通过 / AI 评估通过 / 人工确认通过 / 尚未验证。

## 8. 分支与提交

- 工作分支：`claude/install-claude-hud-d51E6`，它也是 GitHub 默认分支，定时工作流都跑在这里。
- 工作流会并发提交，推送前先 `git fetch && git merge`。
- 不合并 `claude/us-stock-opportunities-htj5ur`。
- 不开 PR，除非用户要求。
