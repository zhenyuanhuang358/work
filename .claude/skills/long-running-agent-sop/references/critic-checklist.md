# Critic 执行检查清单

**Critic 必须真实运行（Playwright / API 请求 / Console 监控），不能只读代码。**

对照 Contract 的判定：逐条 acceptance_tests 验证，逐条 failure_conditions 检查。
有一条 failure_condition 触发即判定失败，不允许「基本通过」。

---

## UI 层

- [ ] 所有可点击元素是否真实响应
- [ ] 是否存在假成功（UI 显示 OK 但后端未处理）
- [ ] 是否有卡顿或无响应（超过 performance_constraints.max_response_ms）

## 后端层

- [ ] API 是否真实返回预期数据
- [ ] 数据是否持久化（重启后验证）
- [ ] 并发场景是否数据错乱（模拟 performance_constraints.concurrent_users）

## Runtime

- [ ] 控制台是否有 Error 级别日志
- [ ] 是否存在内存泄漏或 CPU 异常
- [ ] 是否满足 performance_constraints 全部指标

---

## 判定输出格式

```json
{
  "verdict": "PASS | FAIL",
  "failed_conditions": ["触发的 failure_condition 原文"],
  "passed_tests": ["通过的 acceptance_test 原文"],
  "evidence": ["截图路径 / 日志片段 / API 响应"],
  "recommendation": "CONTINUE | RESTART"
}
```

FAIL 时必须填写 `failed_conditions` 和 `evidence`，禁止空字段。
