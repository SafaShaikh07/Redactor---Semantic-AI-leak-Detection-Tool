import time
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from corpus import most_similar
from pattern_detector import scan_and_redact
from db import log_check, get_recent_logs, get_metrics

RESULTS_FILE = Path(__file__).parent / "coverage_results.json"

app = FastAPI(title="Redactor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CheckRequest(BaseModel):
    text: str


class MatchSpan(BaseModel):
    start: int
    end: int
    reason: str
    severity: str = "redact"


class CheckResponse(BaseModel):
    action: str
    reason: str
    matched_doc: Optional[str] = None
    redacted_text: Optional[str] = None
    matches: List[MatchSpan] = []
    reason_detail: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Redactor (Semantic AI Leak Detection - Live Protection Log)</title>
    <style>
        body {
            background-color: #0d0d0d;
            color: #e0e0e0;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 24px;
        }
        h1 {
            color: #ffffff;
            font-size: 24px;
            margin-bottom: 20px;
            font-weight: 600;
        }
        .stats-bar {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .stat-card {
            background-color: #141414;
            border: 1px solid #222222;
            border-radius: 8px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .stat-label {
            color: #888888;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 500;
        }
        .stat-value {
            color: #ffffff;
            font-size: 22px;
            font-weight: 700;
            font-family: monospace, system-ui;
        }
        .val-block { color: #e57373; }
        .val-redact { color: #ffb74d; }
        .table-container {
            overflow-x: auto;
            border-radius: 8px;
            border: 1px solid #222222;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 14px;
        }
        th, td {
            padding: 12px 16px;
            border-bottom: 1px solid #222222;
        }
        th {
            background-color: #1a1a1a;
            color: #888888;
            font-weight: 500;
            text-transform: uppercase;
            font-size: 12px;
            letter-spacing: 0.5px;
        }
        tr.action-allow {
            background-color: rgba(46, 125, 50, 0.15);
            color: #81c784;
        }
        tr.action-redact {
            background-color: rgba(245, 124, 0, 0.15);
            color: #ffb74d;
        }
        tr.action-block {
            background-color: rgba(211, 47, 47, 0.15);
            color: #e57373;
        }
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
        }
        .badge-allow { background: rgba(76, 175, 80, 0.2); color: #81c784; }
        .badge-redact { background: rgba(255, 152, 0, 0.2); color: #ffb74d; }
        .badge-block { background: rgba(244, 67, 54, 0.2); color: #e57373; }
    </style>
</head>
<body>
    <h1>Redactor (Semantic AI Leak Detection - Live Protection Log)</h1>

    <div class="stats-bar">
        <div class="stat-card">
            <span class="stat-label">Total Checks</span>
            <span class="stat-value" id="stat-total">0</span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Block Rate</span>
            <span class="stat-value val-block" id="stat-block-rate">0%</span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Redact Rate</span>
            <span class="stat-value val-redact" id="stat-redact-rate">0%</span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Avg Latency</span>
            <span class="stat-value" id="stat-latency">0 ms</span>
        </div>
    </div>

    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th style="width: 20%;">Time</th>
                    <th style="width: 20%;">Action</th>
                    <th style="width: 60%;">Reason</th>
                </tr>
            </thead>
            <tbody id="logs-body">
                <tr><td colspan="3" style="text-align:center; color:#666;">Loading logs...</td></tr>
            </tbody>
        </table>
    </div>

    <details class="coverage-section" style="margin-top: 32px; border: 1px solid #222; border-radius: 8px; padding: 16px; background: #141414;">
        <summary style="cursor: pointer; font-weight: 600; font-size: 16px; color: #ffffff;">
            Detection Coverage Report
        </summary>
        <div style="margin-top: 16px;">
            <p id="coverage-summary" style="color: #89b4fa; font-weight: 500; font-size: 14px; margin-bottom: 16px;">Loading coverage results...</p>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Probe Test Case</th>
                            <th>Regex</th>
                            <th>Semantic</th>
                            <th>Action</th>
                            <th>Detail</th>
                        </tr>
                    </thead>
                    <tbody id="coverage-body">
                        <tr><td colspan="6" style="text-align:center; color:#666;">No coverage data available</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </details>

    <script>
        async function fetchMetrics() {
            try {
                const res = await fetch('/metrics');
                const data = await res.json();
                document.getElementById('stat-total').textContent = data.total_checks || 0;
                document.getElementById('stat-block-rate').textContent = (data.rates ? data.rates.block_rate_pct : 0) + '%';
                document.getElementById('stat-redact-rate').textContent = (data.rates ? data.rates.redact_rate_pct : 0) + '%';
                document.getElementById('stat-latency').textContent = (data.latency ? data.latency.avg_ms : 0) + ' ms';
            } catch (err) {
                console.error('Error fetching metrics:', err);
            }
        }

        async function fetchLogs() {
            try {
                const res = await fetch('/logs');
                const data = await res.json();
                const tbody = document.getElementById('logs-body');
                if (!data || data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; color:#666;">No logs available</td></tr>';
                    return;
                }
                tbody.innerHTML = data.map(log => {
                    const actionClass = `action-${log.action.toLowerCase()}`;
                    const badgeClass = `badge-${log.action.toLowerCase()}`;
                    const timeStr = log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '-';
                    const detailStr = (log.reason_detail || log.reason || '').replace(/"/g, '&quot;');
                    return `
                        <tr class="${actionClass}">
                            <td>${timeStr}</td>
                            <td><span class="badge ${badgeClass}">${log.action}</span></td>
                            <td title="${detailStr}" style="cursor: help; text-decoration: underline dotted #666;">${log.reason}</td>
                        </tr>
                    `;
                }).join('');
            } catch (err) {
                console.error('Error fetching logs:', err);
            }
        }

        async function fetchCoverage() {
            try {
                const res = await fetch('/coverage');
                if (!res.ok) return;
                const data = await res.json();
                
                if (data.summary_line) {
                    document.getElementById('coverage-summary').textContent = data.summary_line;
                }
                
                if (data.redteam && data.redteam.cases) {
                    const tbody = document.getElementById('coverage-body');
                    tbody.innerHTML = data.redteam.cases.map(c => {
                        const actionClass = `action-${c.action.toLowerCase()}`;
                        const badgeClass = `badge-${c.action.toLowerCase()}`;
                        return `
                            <tr class="${actionClass}">
                                <td>${c.id}</td>
                                <td>${c.name}</td>
                                <td>${c.regex}</td>
                                <td>${c.semantic}</td>
                                <td><span class="badge ${badgeClass}">${c.action}</span></td>
                                <td>${c.detail}</td>
                            </tr>
                        `;
                    }).join('');
                }
            } catch (err) {
                console.error('Error fetching coverage:', err);
            }
        }

        function refreshData() {
            fetchMetrics();
            fetchLogs();
        }

        refreshData();
        fetchCoverage();
        setInterval(refreshData, 5000);
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)


@app.get("/logs")
def get_logs():
    return get_recent_logs(limit=50)


@app.get("/metrics")
def get_metrics_endpoint():
    return get_metrics()


@app.get("/coverage")
def get_coverage_endpoint():
    if RESULTS_FILE.exists():
        try:
            return JSONResponse(content=json.loads(RESULTS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return JSONResponse(content={"summary_line": "No coverage results recorded yet.", "redteam": {"cases": []}})


@app.post("/check", response_model=CheckResponse)
def check_text(request: CheckRequest):
    t0 = time.perf_counter()
    input_text = request.text
    input_len = len(input_text)

    # Secret scanning
    secret_redacted_text, has_secrets, secret_reasons, raw_matches = scan_and_redact(input_text)

    # Semantic similarity check
    doc_name, score = most_similar(input_text)
    is_semantic_match = score > 0.45

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    matches = [
        MatchSpan(
            start=m["start"],
            end=m["end"],
            reason=m["reason"],
            severity=m.get("severity", "redact")
        )
        for m in raw_matches
    ]

    if is_semantic_match and not matches:
        matches.append(MatchSpan(
            start=0,
            end=input_len,
            reason="semantic match",
            severity="redact"
        ))

    # Check for BLOCK-level severity priority
    has_block = any(m.severity == "block" for m in matches)

    # Construct structured details
    detail_parts = []
    if raw_matches:
        pattern_details = [f"{m['reason']} ({m['end'] - m['start']} chars)" for m in raw_matches]
        detail_parts.append("; ".join(pattern_details))

    if is_semantic_match:
        sim_pct = int(score * 100)
        detail_parts.append(f"{sim_pct}% match to {doc_name}")

    reason_detail = " | ".join(detail_parts) if detail_parts else None

    if has_block:
        action = "block"
        matched_doc = doc_name if is_semantic_match else None

        if has_secrets and is_semantic_match:
            reason = f"secret ({', '.join(secret_reasons)}) & semantic match"
        elif has_secrets:
            reason = ", ".join(secret_reasons)
        else:
            reason = "semantic match"

        log_check(input_len, action, reason, matched_doc, reason_detail, latency_ms)
        return CheckResponse(
            action=action,
            reason=reason,
            matched_doc=matched_doc,
            redacted_text=None,
            matches=matches,
            reason_detail=reason_detail
        )

    if has_secrets or is_semantic_match:
        action = "redact"
        matched_doc = doc_name if is_semantic_match else None

        if has_secrets and is_semantic_match:
            reason = f"secret ({', '.join(secret_reasons)}) & semantic match"
            redacted_text = secret_redacted_text
        elif has_secrets:
            reason = ", ".join(secret_reasons)
            redacted_text = secret_redacted_text
        else:
            reason = "semantic match"
            redacted_text = "[REDACTED: semantic match]"

        log_check(input_len, action, reason, matched_doc, reason_detail, latency_ms)
        return CheckResponse(
            action=action,
            reason=reason,
            matched_doc=matched_doc,
            redacted_text=redacted_text,
            matches=matches,
            reason_detail=reason_detail
        )

    action = "allow"
    reason = "no match"
    log_check(input_len, action, reason, None, None, latency_ms)
    return CheckResponse(
        action=action,
        reason=reason,
        matched_doc=None,
        redacted_text=None,
        matches=[],
        reason_detail=None
    )
