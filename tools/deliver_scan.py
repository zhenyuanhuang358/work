#!/usr/bin/env python3
"""把已验证的期权扫描报告登记为已交付，并生成可复查的机器回执。"""

from __future__ import annotations

import argparse
import json
import os

import options_state as state


def deliver(manifest_path: str, scan_path: str, report_path: str,
            verification_receipt_path: str, output_path: str | None = None) -> dict:
    manifest = state.read_json(manifest_path)
    scan = state.read_json(scan_path)
    verification_receipt = state.read_json(verification_receipt_path)
    if not manifest or not scan or not verification_receipt:
        raise FileNotFoundError("交付所需的 manifest、scan 或验证回执不存在")
    if manifest.get("stage") not in {"VERIFIED", "DELIVERED"}:
        raise ValueError(f"只有 VERIFIED 运行才能交付，当前为 {manifest.get('stage')}")

    run_id = manifest.get("run_id")
    observed_ids = {
        manifest.get("run_id"),
        scan.get("run_id") or scan.get("id"),
        verification_receipt.get("run_id"),
    }
    if observed_ids != {run_id}:
        raise ValueError(f"交付文件运行编号不一致：{sorted(str(x) for x in observed_ids)}")
    if not os.path.exists(report_path):
        raise FileNotFoundError(report_path)

    report_sha = state.sha256_file(report_path)
    expected_report_sha = (scan.get("verification") or {}).get("report_sha256")
    if not expected_report_sha or report_sha != expected_report_sha:
        raise ValueError("报告内容与 scan 中的验证哈希不一致，请重新验证")
    if verification_receipt.get("report_sha256") != report_sha:
        raise ValueError("报告内容与验证回执哈希不一致，请重新验证")
    if verification_receipt.get("verification_passed") is not True:
        raise ValueError("验证回执未通过，禁止登记交付")
    if verification_receipt.get("delivery_status") != scan.get("delivery_status"):
        raise ValueError("scan 与验证回执的交付状态不一致")

    output_path = output_path or report_path + ".delivery.json"
    stable = {
        "schema_version": 1,
        "run_id": run_id,
        "delivery_status": scan.get("delivery_status"),
        "actionable": scan.get("actionable") is True,
        "blockers": [
            {"gate": name, "status": gate.get("status"), "reason": gate.get("reason") or gate.get("reasons")}
            for name, gate in (scan.get("gates") or {}).items()
            if gate.get("pass") is not True
        ],
        "artifacts": {
            "manifest": {"path": os.path.abspath(manifest_path)},
            "scan": {"path": os.path.abspath(scan_path), "sha256": state.sha256_file(scan_path)},
            "report": {"path": os.path.abspath(report_path), "sha256": report_sha},
            "verification_receipt": {
                "path": os.path.abspath(verification_receipt_path),
                "sha256": state.sha256_file(verification_receipt_path),
            },
        },
    }
    existing = state.read_json(output_path)
    if existing:
        comparable = {key: value for key, value in existing.items() if key != "delivered_at"}
        if comparable != stable:
            raise ValueError(f"交付回执冲突，禁止覆盖：{output_path}")
        delivery = existing
    else:
        delivery = {**stable, "delivered_at": state.utc_now()}
        state.atomic_write_json(output_path, delivery)

    if manifest.get("stage") != "DELIVERED":
        state.transition(manifest_path, "DELIVERED", artifacts={
            "delivery": {"path": os.path.abspath(output_path), "sha256": state.sha256_file(output_path)}
        })
    return delivery


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--scan", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--verification-receipt", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()
    result = deliver(args.manifest, args.scan, args.report, args.verification_receipt, args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
