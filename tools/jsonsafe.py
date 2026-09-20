#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""严格 JSON 加载器 —— profile 1.1u 第 1 条的真正承载物。

**为什么不是静态检查**：先写了一版 AST 检查器，想「扫出脚本里用的键名，
拿真实文件核对存不存在」。在本仓库上实测：**14 个脚本里只绑定到 1 个变量、
核对 1 处键**——因为真实代码里路径几乎都来自函数参数（`def load(path)`）
或计算出的常量（`os.path.join(REPO, ...)`），静态分析追不动。
**一个只核对 1 处还打 ✅ 的检查器是在装绿。**

**所以改做结构性修复**：1.1u 的事故形态是
    d.get("closed")   # 键不存在 → 静默返回 None → 汇总里出现 closed 0 项
问题不在「我没检查」，在 **`.get()` 把拼写错误伪装成了数据为空**。
1.1u 自己的通用推论就写了：
    「取数用直接索引让它抛错，只在确实允许缺失时才用 get。」

本模块把这条变成机制：经 `load()` 读进来的 dict，
**`.get(k)` 不给默认值时，遇到不存在的键会抛错**，并在错误信息里列出实际键名；
`.get(k, default)` 显式给了默认值则照常工作 —— 因为那是明确表达了「允许缺失」。

用法：
    from jsonsafe import load
    d = load("burry_holdings.json")
    d.get("closed")          # ⛔ KeyError：键不存在，且列出实际键名
    d.get("closed", [])      # ✓ 显式允许缺失，返回 []
    d["changes"]             # ✓ 正常；缺失时本来就抛 KeyError（响亮失败）
"""
import json
import os


class StrictDict(dict):
    """`.get(k)` 不带默认值时，对不存在的键抛错而不是静默返回 None。"""

    __slots__ = ("_src",)

    def __init__(self, data, src=""):
        super().__init__(data)
        self._src = src

    _MISSING = object()

    def get(self, key, default=_MISSING):
        if key in self:
            return _wrap(super().get(key), self._src)
        if default is StrictDict._MISSING:
            raise KeyError(
                f"{self._src or '<dict>'} 里没有键 {key!r}。"
                f" 实际键名：{sorted(self)[:12]}"
                f"{' …' if len(self) > 12 else ''}。"
                f" 若确实允许缺失，请显式写 .get({key!r}, 默认值) —— "
                f"（profile 1.1u：.get() 对拼错的键不报错，"
                f"会把拼写错误伪装成数据为空）"
            )
        return default

    def __getitem__(self, key):
        try:
            return _wrap(super().__getitem__(key), self._src)
        except KeyError:
            raise KeyError(
                f"{self._src or '<dict>'} 里没有键 {key!r}。实际键名：{sorted(self)[:12]}"
            ) from None


def _wrap(v, src):
    if isinstance(v, dict) and not isinstance(v, StrictDict):
        return StrictDict(v, src)
    if isinstance(v, list):
        return [_wrap(x, src) for x in v]
    return v


def load(path, encoding="utf-8"):
    """读 JSON 产物，返回 StrictDict（嵌套的 dict 也是）。"""
    with open(path, encoding=encoding) as f:
        return _wrap(json.load(f), os.path.basename(path))


def loads(text, src="<str>"):
    """从字符串读（例如 `git show HEAD:x.json` 的输出），同样返回 StrictDict。"""
    return _wrap(json.loads(text), src)


def keys_report(d, label=""):
    """1.1u 第 1 条的字面执行：读子结构前先把键名打出来。"""
    print(f"  {label or '<dict>'} 顶层键：{sorted(d) if isinstance(d, dict) else type(d).__name__}")
    return d
