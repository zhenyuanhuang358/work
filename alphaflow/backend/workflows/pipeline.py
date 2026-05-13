"""
AlphaFlow research pipeline — 6 sequential nodes.

NODE 1: fetch_company_data     → pull financials + context
NODE 2: fetch_transcript       → pull guidance text for tone analysis
NODE 3: extract_metrics        → LLM JSON extraction
NODE 4: analyze_tone           → LLM management tone scoring
NODE 5: generate_memo          → LLM full investment memo
NODE 6: export_pdf             → reportlab PDF generation
"""
import json
import logging
import traceback
from dataclasses import dataclass, field
from typing import Optional

from backend.services.financial_client import get_company_data
from backend.services.llm_client import extract_metrics, analyze_tone, generate_memo
from backend.reports.pdf_generator import generate_pdf
from database.db import update_report_step, update_report_result, update_report_error

log = logging.getLogger(__name__)


@dataclass
class PipelineState:
    report_id: str
    ticker: str
    company_data: dict = field(default_factory=dict)
    transcript_text: str = ""
    metrics: dict = field(default_factory=dict)
    tone: dict = field(default_factory=dict)
    memo: str = ""
    pdf_bytes: bytes = b""
    error: Optional[str] = None


async def run_pipeline(report_id: str, ticker: str) -> None:
    """Execute the full research pipeline for a given ticker."""
    state = PipelineState(report_id=report_id, ticker=ticker.upper())

    nodes = [
        ("fetch_company_data", _fetch_company_data),
        ("fetch_transcript", _fetch_transcript),
        ("extract_metrics", _extract_metrics),
        ("analyze_tone", _analyze_tone),
        ("generate_memo", _generate_memo),
        ("export_pdf", _export_pdf),
    ]

    for step_name, node_fn in nodes:
        try:
            await update_report_step(report_id, step_name, "running")
            log.info(f"[{report_id}] Running node: {step_name}")
            state = await node_fn(state)
            await update_report_step(report_id, step_name, "done")
        except Exception as exc:
            log.error(f"[{report_id}] Node {step_name} failed: {exc}\n{traceback.format_exc()}")
            await update_report_error(report_id, step_name, str(exc))
            return

    log.info(f"[{report_id}] Pipeline complete — PDF {len(state.pdf_bytes):,} bytes")


# ── Node implementations ──────────────────────────────────────────────────────

async def _fetch_company_data(state: PipelineState) -> PipelineState:
    state.company_data = await get_company_data(state.ticker)
    return state


async def _fetch_transcript(state: PipelineState) -> PipelineState:
    """
    Build the text block used for management tone analysis.
    Production: fetches earnings transcript from AlphaVantage / SEC 8-K.
    Demo: uses management commentary embedded in financial data.
    """
    fin = state.company_data.get("financials", {})
    guidance = fin.get("guidance", {})
    news = state.company_data.get("context", {}).get("recent_news", [])

    lines = [
        f"Quarterly Earnings Release — {state.ticker} {fin.get('quarter', '')}",
        "",
        "Management Commentary on Guidance:",
        guidance.get("management_commentary", ""),
        "",
        "Recent Company Developments:",
    ] + [f"- {n}" for n in news]

    state.transcript_text = "\n".join(lines)
    return state


async def _extract_metrics(state: PipelineState) -> PipelineState:
    state.metrics = await extract_metrics(state.company_data["financials"])
    return state


async def _analyze_tone(state: PipelineState) -> PipelineState:
    state.tone = await analyze_tone(state.transcript_text)
    return state


async def _generate_memo(state: PipelineState) -> PipelineState:
    state.memo = await generate_memo(
        metrics=state.metrics,
        tone=state.tone,
        context=state.company_data.get("context", {}),
    )
    return state


async def _export_pdf(state: PipelineState) -> PipelineState:
    pdf_bytes = generate_pdf(
        company_data=state.company_data,
        metrics=state.metrics,
        tone=state.tone,
        memo=state.memo,
    )
    state.pdf_bytes = pdf_bytes

    # Save to disk + update DB with URL
    import os, aiofiles
    reports_dir = os.environ.get("REPORTS_DIR", "/tmp/alphaflow_reports")
    os.makedirs(reports_dir, exist_ok=True)
    pdf_path = os.path.join(reports_dir, f"{state.report_id}.pdf")

    async with aiofiles.open(pdf_path, "wb") as f:
        await f.write(pdf_bytes)

    await update_report_result(
        report_id=state.report_id,
        pdf_path=pdf_path,
        summary=state.memo[:500],
    )
    return state
