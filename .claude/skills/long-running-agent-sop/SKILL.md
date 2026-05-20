---
name: long-running-agent-sop
description: |
  长时间运行 AI Agent 工作手册。面向 Code Agent / 多 Agent 系统 / 自动化研发系统。
  核心原则：不允许大模型既负责生成，又负责验证自己。
  触发词：「长程 Agent」「Builder」「Critic」「Planner」「三权分立」
  「Breadcrumbs」「Contract」「自我验证失效」「多 Agent 架构」「Agent SOP」
---

# 长时间运行 Agent SOP

> 核心原则：**不允许生成者同时担任验证者。**

---

## 三个底层死因（快速诊断）

| 死因 | 症状 | 根治方法 |
|------|------|---------|
| **Context Rot** | 早期目标被稀释，输出越来越像样但越来越没用 | 状态外挂文件系统，不依赖上下文 |
| **Context Anxiety** | 模型回避复杂修改，提前宣告完成 | 强制 Breadcrumbs 检查点，禁止自我宣告 |
| **自我验证失效** | 自己写代码、自己测试、自己说通过 | Critic 必须拥有独立上下文 + 真实工具 |

---

## 核心架构：三权分立

| 角色 | 职责 | 禁止 |
|------|------|------|
| **Planner** | 业务目标、Sprint 拆分、验收边界 | 写代码、定技术路线 |
| **Builder** | 实现、修改、重构、输出 Breadcrumbs | 自我验收、修改 Contract |
| **Critic** | 证明 Builder 是错的 | 共享 Builder 上下文、只读代码不运行 |

**Critic 的目标不是帮助 Builder 成功——是尽最大可能证明 Builder 是错的。**

运行拓扑：
```
USER GOAL → PLANNER → CONTRACT → BUILDER → CRITIC → PASS / RESTART
                          ↑____________FEEDBACK LOOP_______________|
```

---

## Breadcrumbs（每轮 Builder 结束必须输出）

```json
{
  "task": "本轮完成了什么",
  "files_changed": ["path/to/file"],
  "known_issues": ["已知但未修复的问题"],
  "assumptions_made": ["本轮做了哪些假设"],
  "next_steps": ["下一轮应该做什么"],
  "confidence": 0.0
}
```

---

## 推荐目录结构

```
agent-system/
├── contracts/      # Contract 文件
├── tasks/          # Sprint 任务分解
├── traces/         # Builder 和 Critic 的决策日志
├── checkpoints/    # Breadcrumbs
└── artifacts/      # 最终交付物
```

---

## Spoke 加载表

| 场景 | 加载文件 |
|------|---------|
| 制定 Contract（开发前） | `references/contract-template.md` |
| Critic 执行验证 | `references/critic-checklist.md` |
| Builder 节点 System Prompt | `references/builder-system-prompt.md` |

---

## Restart 触发条件（满足任意一条即重启）

- 连续失败次数超过 `max_failed_iterations`
- Critic 判定架构存在根本冲突
- 状态污染导致无法确定系统当前真实状态
- Contract 核心条款无法在现有架构下满足

**重启时**：保留 Contract 和 traces，清空 Builder 上下文，从头实现。

---

## 元认知

当前 SOP 的复杂度部分是在补偿模型能力的不足。随着模型升级，节点数量和 Prompt 复杂度都会下降。
**唯一不会废弃的原则**：不允许生成者同时担任验证者。
