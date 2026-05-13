"""
AlphaFlow FastAPI — two endpoints only.

POST /analyze      { "ticker": "NVDA" }  → { "report_id": "rpt_xxx", "status": "processing" }
GET  /report/{id}  → { status, pdf_url, summary, ... }
GET  /report/{id}/download → serves the PDF file
"""
import os
import sys
import logging
from pathlib import Path

# Ensure project root is on sys.path when run directly
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

from database.db import create_report, get_report
from backend.workflows.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="AlphaFlow API",
    description="Institutional-quality AI equity research reports",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPORTS_DIR = os.environ.get("REPORTS_DIR", "/tmp/alphaflow_reports")


class AnalyzeRequest(BaseModel):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def clean_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v.isalpha() or len(v) > 5:
            raise ValueError("Invalid ticker symbol")
        return v


@app.post("/analyze", status_code=202)
async def analyze(req: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    Kick off a research pipeline for the given ticker.
    Returns immediately with a report_id to poll.
    """
    report_id = create_report(req.ticker)
    background_tasks.add_task(run_pipeline, report_id, req.ticker)
    return {"report_id": report_id, "status": "processing", "ticker": req.ticker}


@app.get("/report/{report_id}")
async def get_report_status(report_id: str):
    """Poll for report status. Returns pdf_url when complete."""
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    response = {
        "report_id": report["id"],
        "ticker": report["ticker"],
        "status": report["status"],
        "current_step": report["current_step"],
        "summary": report["summary"],
        "created_at": report["created_at"],
    }

    if report["status"] == "complete" and report["pdf_path"]:
        response["pdf_url"] = f"/report/{report_id}/download"

    if report["status"] == "error":
        response["error"] = report["error"]

    return response


@app.get("/report/{report_id}/download")
async def download_report(report_id: str):
    """Serve the generated PDF."""
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report["status"] != "complete" or not report.get("pdf_path"):
        raise HTTPException(status_code=404, detail="Report not ready yet")

    pdf_path = report["pdf_path"]
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"AlphaFlow_{report['ticker']}_{report_id}.pdf",
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "alphaflow-api"}
