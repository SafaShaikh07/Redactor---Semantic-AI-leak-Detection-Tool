from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
from corpus import most_similar
from pattern_detector import scan_and_redact
from db import log_check, get_recent_logs

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
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Action</th>
                    <th>Reason</th>
                    <th>Matched Doc</th>
                </tr>
            </thead>
            <tbody id="logs-body">
                <tr><td colspan="4" style="text-align:center; color:#666;">Loading logs...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        async function fetchLogs() {
            try {
                const res = await fetch('/logs');
                const data = await res.json();
                const tbody = document.getElementById('logs-body');
                if (!data || data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#666;">No logs available</td></tr>';
                    return;
                }
                tbody.innerHTML = data.map(log => {
                    const actionClass = `action-${log.action.toLowerCase()}`;
                    const badgeClass = `badge-${log.action.toLowerCase()}`;
                    const timeStr = log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '-';
                    const docStr = log.matched_doc || '-';
                    return `
                        <tr class="${actionClass}">
                            <td>${timeStr}</td>
                            <td><span class="badge ${badgeClass}">${log.action}</span></td>
                            <td>${log.reason}</td>
                            <td>${docStr}</td>
                        </tr>
                    `;
                }).join('');
            } catch (err) {
                console.error('Error fetching logs:', err);
            }
        }

        fetchLogs();
        setInterval(fetchLogs, 5000);
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)


@app.get("/logs")
def get_logs():
    return get_recent_logs(limit=50)


@app.post("/check", response_model=CheckResponse)
def check_text(request: CheckRequest):
    input_text = request.text
    input_len = len(input_text)

    # Secret scanning
    secret_redacted_text, has_secrets, secret_reasons, raw_matches = scan_and_redact(input_text)

    # Semantic similarity check
    doc_name, score = most_similar(input_text)
    is_semantic_match = score > 0.45

    matches = [
        MatchSpan(
            start=m["start"],
            end=m["end"],
            reason=m["reason"],
            severity="redact"
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

        log_check(input_len, action, reason, matched_doc)
        return CheckResponse(
            action=action,
            reason=reason,
            matched_doc=matched_doc,
            redacted_text=redacted_text,
            matches=matches
        )

    action = "allow"
    reason = "no match"
    log_check(input_len, action, reason, None)
    return CheckResponse(
        action=action,
        reason=reason,
        matched_doc=None,
        redacted_text=None,
        matches=[]
    )
