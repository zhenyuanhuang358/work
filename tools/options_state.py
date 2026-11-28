#!/usr/bin/env python3
"""期权扫描的持久状态、原子写入与可恢复运行记录。

本模块不包含交易策略。它只回答三个工程问题：
1. 这次运行进行到哪里；2. 同一个运行是否已经触发过；3. 当前持仓是否足够新、足够可信。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone


SCHEMA_VERSION = 1
STAGES = (
    "CREATED",
    "FETCHING",
    "FETCHED",
    "ANALYZING",
    "ANALYZED",
    "DRAFTED",
    "VERIFIED",
    "DELIVERED",
)
FAILURE_STAGES = {
    "FAILED_FETCH",
    "FAILED_DATA",
    "FAILED_ANALYSIS",
    "FAILED_VERIFY",
}
RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return default


def atomic_write_json(path: str, data) -> None:
    """同目录临时文件 + replace，避免中断留下半个 JSON。"""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".tmp-options-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2, default=str)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reserve_fetch(path: str, run_id: str) -> dict:
    """为连接器取数预留稳定批次；重复调用返回同一批次，不生成第二次触发。"""
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("run_id 只允许字母、数字、点、下划线和连字符，最长 80 字符")
    current = read_json(path)
    if current is not None:
        if current.get("run_id") != run_id:
            raise ValueError(f"取数回执冲突：{path} 已属于 {current.get('run_id')}")
        return current
    now = utc_now()
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "trigger": f"scan-{run_id}",
        "status": "RESERVED",
        "created_at": now,
        "updated_at": now,
        "remote_commit": None,
        "artifacts": {},
    }
    atomic_write_json(path, receipt)
    return receipt


def complete_fetch(path: str, *, trigger: str, commit: str, artifacts: dict | None = None) -> dict:
    receipt = read_json(path)
    if not receipt:
        raise FileNotFoundError(path)
    if receipt.get("trigger") != trigger:
        raise ValueError(f"取数批次冲突：预留 {receipt.get('trigger')}，实际 {trigger}")
    receipt.update({
        "status": "FETCHED",
        "updated_at": utc_now(),
        "remote_commit": commit,
        "artifacts": artifacts or {},
    })
    atomic_write_json(path, receipt)
    return receipt


def create_or_load_manifest(path: str, run_id: str, *, asof: str, trigger: str | None = None) -> dict:
    current = read_json(path)
    if current is not None:
        if current.get("run_id") != run_id:
            raise ValueError(f"运行记录冲突：{path} 属于 {current.get('run_id')}，不是 {run_id}")
        if trigger and current.get("trigger") not in (None, trigger):
            raise ValueError(f"批次冲突：已登记 {current.get('trigger')}，本次要求 {trigger}")
        if trigger and current.get("trigger") is None:
            current["trigger"] = trigger
            current["updated_at"] = utc_now()
            atomic_write_json(path, current)
        return current

    now = utc_now()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "asof": asof,
        "trigger": trigger,
        "stage": "CREATED",
        "created_at": now,
        "updated_at": now,
        "history": [{"stage": "CREATED", "at": now}],
        "artifacts": {},
        "error": None,
    }
    atomic_write_json(path, manifest)
    return manifest


def transition(path: str, stage: str, *, detail: str | None = None, artifacts: dict | None = None) -> dict:
    if stage not in STAGES and stage not in FAILURE_STAGES:
        raise ValueError(f"未知运行阶段：{stage}")
    manifest = read_json(path)
    if not manifest:
        raise FileNotFoundError(path)

    previous = manifest["stage"]
    if previous == stage:
        return manifest
    if previous in FAILURE_STAGES and stage not in {"FETCHING", "ANALYZING", "DRAFTED"}:
        raise ValueError(f"失败状态 {previous} 只能从可重试阶段恢复，不能跳到 {stage}")
    if stage in STAGES and previous in STAGES:
        if STAGES.index(stage) < STAGES.index(previous):
            raise ValueError(f"运行阶段不能倒退：{previous} → {stage}")

    now = utc_now()
    event = {"stage": stage, "at": now}
    if detail:
        event["detail"] = detail
    manifest["stage"] = stage
    manifest["updated_at"] = now
    try:
        started = datetime.fromisoformat(manifest["created_at"].replace("Z", "+00:00"))
        finished = datetime.fromisoformat(now.replace("Z", "+00:00"))
        manifest["elapsed_seconds"] = max(0.0, round((finished - started).total_seconds(), 3))
        event["elapsed_seconds"] = manifest["elapsed_seconds"]
    except (KeyError, TypeError, ValueError):
        pass
    manifest.setdefault("history", []).append(event)
    if artifacts:
        manifest.setdefault("artifacts", {}).update(artifacts)
    manifest["error"] = {"stage": stage, "detail": detail, "at": now} if stage in FAILURE_STAGES else None
    atomic_write_json(path, manifest)
    return manifest


def inspect_positions(path: str, *, now: datetime | None = None, max_age_hours: float = 24.0) -> dict:
    """返回持仓门禁结果；缺失、未确认、过期均保守阻断具体张数建议。"""
    now = now or datetime.now(timezone.utc)
    snapshot = read_json(path)
    result = {
        "path": path,
        "status": "MISSING",
        "pass": False,
        "as_of": None,
        "age_hours": None,
        "confirmed": False,
        "positions": [],
        "reason": "当前持仓快照不存在",
    }
    if not snapshot:
        return result

    result.update({
        "as_of": snapshot.get("as_of"),
        "confirmed": snapshot.get("confirmed") is True,
        "positions": snapshot.get("positions") or [],
    })
    if not result["confirmed"]:
        result.update(status="UNCONFIRMED", reason="当前持仓尚未由用户或券商截图确认")
        return result
    if not result["as_of"]:
        result.update(status="INVALID", reason="持仓快照缺少 as_of")
        return result
    try:
        stamp = datetime.fromisoformat(result["as_of"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        result.update(status="INVALID", reason="持仓快照 as_of 不是有效 ISO 时间")
        return result
    age = max(0.0, (now - stamp.astimezone(timezone.utc)).total_seconds() / 3600)
    result["age_hours"] = round(age, 2)
    if age > max_age_hours:
        result.update(status="STALE", reason=f"持仓快照已 {age:.1f} 小时，超过 {max_age_hours:g} 小时上限")
        return result
    result.update(status="CURRENT", **{"pass": True}, reason="持仓快照已确认且在时限内")
    return result


def final_delivery_state(scan: dict, verification_passed: bool) -> tuple[str, bool]:
    gates = scan.get("gates") or {}
    required = ("data", "market", "position")
    ready = verification_passed and all((gates.get(name) or {}).get("pass") is True for name in required)
    if ready:
        return "READY_FOR_BROKER_CHECK", True
    if verification_passed:
        return "VERIFIED_WITH_BLOCKS", False
    return "FAILED_VERIFY", False
