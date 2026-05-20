# Contract 模板

Contract 是系统最关键的单一制品。没有 Contract，Builder 会无限自我解释、自我合理化、自我放行。
Contract 是 Critic 唯一的判断基准。

**必须在开发前由 Critic 参与制定。**

---

## 模板

```json
{
  "goal": "一句话描述业务目标",
  "acceptance_tests": [
    "用户可以做 X",
    "刷新后 Y 仍存在",
    "Z 和 W 同时操作不冲突"
  ],
  "failure_conditions": [
    "操作后页面无响应超过 2 秒",
    "控制台出现任何 Error 级别日志",
    "数据在刷新后丢失",
    "假发送（UI 显示成功但服务端未收到）"
  ],
  "non_negotiables": [
    "必须真实持久化，不允许内存 mock",
    "必须真实网络通信，不允许本地模拟"
  ],
  "performance_constraints": {
    "concurrent_users": 100,
    "max_response_ms": 500
  },
  "restart_policy": {
    "max_failed_iterations": 5,
    "allow_full_rewrite": true
  }
}
```

---

## failure_conditions 写法原则

| 坏的写法 | 好的写法 |
|---------|---------|
| 「性能差」 | 「任意操作响应超过 500ms」 |
| 「有 bug」 | 「控制台出现任何 Error 级别日志」 |
| 「数据不对」 | 「刷新后数据与写入时不一致」 |

越具体、越可观测、越好。有一条 failure_condition 触发即判定失败，不允许「基本通过」。
