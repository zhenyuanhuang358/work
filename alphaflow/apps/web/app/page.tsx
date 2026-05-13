"use client";

import { useState, useEffect, useRef } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const STEPS = [
  { key: "fetch_data", label: "Fetch Financial Data" },
  { key: "fetch_transcript", label: "Fetch Earnings Transcript" },
  { key: "extract_metrics", label: "Extract Key Metrics" },
  { key: "analyze_tone", label: "Analyze Management Tone" },
  { key: "generate_memo", label: "Generate Research Memo" },
  { key: "export_pdf", label: "Export PDF Report" },
];

type ReportStatus = "pending" | "processing" | "complete" | "error";

interface ReportState {
  report_id: string;
  status: ReportStatus;
  current_step?: string;
  summary?: string;
  pdf_url?: string;
  error?: string;
}

type UIState = "idle" | "loading" | "processing" | "complete" | "error";

export default function Home() {
  const [ticker, setTicker] = useState("");
  const [uiState, setUiState] = useState<UIState>("idle");
  const [report, setReport] = useState<ReportState | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => () => stopPolling(), []);

  const startPolling = (reportId: string) => {
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/report/${reportId}`);
        if (!res.ok) return;
        const data: ReportState = await res.json();
        setReport(data);
        if (data.status === "complete") {
          stopPolling();
          setUiState("complete");
        } else if (data.status === "error") {
          stopPolling();
          setErrorMsg(data.error ?? "Pipeline failed");
          setUiState("error");
        } else {
          setUiState("processing");
        }
      } catch {
        // network hiccup — keep polling
      }
    }, 1500);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const t = ticker.trim().toUpperCase();
    if (!t) return;

    setUiState("loading");
    setReport(null);
    setErrorMsg("");

    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: t }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Request failed");
      }
      const data = await res.json();
      setReport(data);
      setUiState("processing");
      startPolling(data.report_id);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Unknown error");
      setUiState("error");
    }
  };

  const handleReset = () => {
    stopPolling();
    setTicker("");
    setReport(null);
    setErrorMsg("");
    setUiState("idle");
  };

  const currentStepIndex = STEPS.findIndex((s) => s.key === report?.current_step);

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center px-4 py-16"
      style={{ backgroundColor: "#0D1B2A" }}
    >
      {/* Logo / header */}
      <div className="mb-10 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-white">
          Alpha<span style={{ color: "#C9A84C" }}>Flow</span>
        </h1>
        <p className="mt-2 text-sm" style={{ color: "#7A9BBF" }}>
          Institutional-grade equity research — in seconds
        </p>
      </div>

      {/* Card */}
      <div
        className="w-full max-w-lg rounded-2xl p-8 shadow-2xl"
        style={{ backgroundColor: "#112236", border: "1px solid #1A3A55" }}
      >
        {/* ── IDLE / INPUT ── */}
        {(uiState === "idle" || uiState === "loading") && (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <label className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#7A9BBF" }}>
              Ticker Symbol
            </label>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase().slice(0, 5))}
              placeholder="e.g. NVDA"
              disabled={uiState === "loading"}
              maxLength={5}
              className="rounded-lg px-4 py-3 text-lg font-mono font-bold uppercase tracking-widest outline-none transition-all"
              style={{
                backgroundColor: "#0D1B2A",
                border: "1px solid #1A6B9A",
                color: "#FFFFFF",
              }}
              autoFocus
            />
            <button
              type="submit"
              disabled={!ticker.trim() || uiState === "loading"}
              className="mt-2 rounded-lg py-3 text-sm font-bold uppercase tracking-widest transition-opacity disabled:opacity-40"
              style={{ backgroundColor: "#1A6B9A", color: "#FFFFFF" }}
            >
              {uiState === "loading" ? "Starting…" : "Generate Report"}
            </button>
          </form>
        )}

        {/* ── PROCESSING ── */}
        {uiState === "processing" && (
          <div className="flex flex-col gap-6">
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-white">
                Analyzing <span style={{ color: "#C9A84C" }}>{report?.ticker}</span>
              </span>
              <span className="text-xs animate-pulse" style={{ color: "#7A9BBF" }}>
                Running…
              </span>
            </div>

            {/* Step tracker */}
            <ol className="flex flex-col gap-3">
              {STEPS.map((step, idx) => {
                const isDone = currentStepIndex > idx || report?.status === "complete";
                const isActive = currentStepIndex === idx && report?.status !== "complete";
                return (
                  <li key={step.key} className="flex items-center gap-3">
                    <span
                      className="h-3 w-3 rounded-full flex-shrink-0 transition-all"
                      style={{
                        backgroundColor: isDone
                          ? "#2ECC71"
                          : isActive
                          ? "#C9A84C"
                          : "#1A3A55",
                        boxShadow: isActive ? "0 0 6px #C9A84C88" : undefined,
                      }}
                    />
                    <span
                      className="text-sm"
                      style={{
                        color: isDone ? "#2ECC71" : isActive ? "#C9A84C" : "#3A5A75",
                        fontWeight: isActive ? 600 : 400,
                      }}
                    >
                      {step.label}
                    </span>
                  </li>
                );
              })}
            </ol>
          </div>
        )}

        {/* ── COMPLETE ── */}
        {uiState === "complete" && report && (
          <div className="flex flex-col gap-6">
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold text-white">
                <span style={{ color: "#C9A84C" }}>{report.ticker}</span> Report Ready
              </span>
              <span
                className="ml-auto rounded-full px-3 py-1 text-xs font-bold"
                style={{ backgroundColor: "#0D3320", color: "#2ECC71" }}
              >
                COMPLETE
              </span>
            </div>

            {report.summary && (
              <p className="text-sm leading-relaxed" style={{ color: "#7A9BBF" }}>
                {report.summary}
              </p>
            )}

            <a
              href={`${API_BASE}/report/${report.report_id}/download`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 rounded-lg py-3 text-sm font-bold uppercase tracking-widest transition-opacity hover:opacity-90"
              style={{ backgroundColor: "#C9A84C", color: "#0D1B2A" }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              Download PDF
            </a>

            <button
              onClick={handleReset}
              className="text-xs underline transition-opacity hover:opacity-70"
              style={{ color: "#7A9BBF" }}
            >
              Analyze another ticker
            </button>
          </div>
        )}

        {/* ── ERROR ── */}
        {uiState === "error" && (
          <div className="flex flex-col gap-4">
            <div
              className="rounded-lg px-4 py-3 text-sm"
              style={{ backgroundColor: "#2A1010", border: "1px solid #8B2020", color: "#FF6B6B" }}
            >
              <strong>Error:</strong> {errorMsg}
            </div>
            <button
              onClick={handleReset}
              className="rounded-lg py-2 text-sm font-bold uppercase tracking-widest transition-opacity hover:opacity-80"
              style={{ backgroundColor: "#1A3A55", color: "#7A9BBF" }}
            >
              Try Again
            </button>
          </div>
        )}
      </div>

      {/* Footer */}
      <p className="mt-8 text-xs" style={{ color: "#2A4A65" }}>
        For informational purposes only. Not investment advice.
      </p>
    </div>
  );
}
