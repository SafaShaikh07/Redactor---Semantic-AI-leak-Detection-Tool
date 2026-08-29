import re
import ipaddress
from typing import Tuple, List

def is_luhn_valid(s: str) -> bool:
    digits = [int(d) for d in s if d.isdigit()]
    if not (13 <= len(digits) <= 19):
        return False
    return sum(d if i % 2 == 0 else (d * 2 - 9 if d * 2 > 9 else d * 2) for i, d in enumerate(reversed(digits))) % 10 == 0

def classify_ip(s: str) -> str:
    try:
        ip = ipaddress.ip_address(s)
        if ip.is_private or ip.is_loopback:
            return "ip_address:private"
        return "ip_address:public"
    except ValueError:
        return ""

def get_severity(reason: str, matched_text: str) -> str:
    if reason in {"private_key_block", "aadhaar_number", "ssn"}:
        return "block"
    if reason == "db_connection_string":
        parts = matched_text.split("@")
        if len(parts) > 1 and ":" in parts[0].split("://")[-1]:
            return "block"
        return "redact"
    return "redact"

PATTERNS = [
    ("api_key", re.compile(r"sk-[A-Za-z0-9]{20,}"), "[REDACTED: api_key]"),
    (
        "db_connection_string",
        re.compile(r"(postgresql|postgres|mysql|mongodb|redis)://[^\s/@:]+(?::[^\s/@]+)?@[^\s/@:]+(?::\d+)?", re.IGNORECASE),
        r"\1://[REDACTED: db_connection_string]"
    ),
    (
        "private_key_block",
        re.compile(r"-----BEGIN[^\n\r]*?PRIVATE KEY-----[\s\S]*?-----END[^\n\r]*?PRIVATE KEY-----", re.IGNORECASE),
        "[REDACTED: private_key_block]"
    ),
    ("email", re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[REDACTED: email]"),
    ("project_codename", re.compile(r"\bProject\s+[A-Z][a-zA-Z0-9_-]*\b"), "[REDACTED: project_codename]"),
    (
        "generic_secret_assignment",
        re.compile(r"\b([a-zA-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PWD|API_KEY|PRIVATE_KEY)[a-zA-Z0-9_]*\s*[:=]\s*)(\S+)", re.IGNORECASE),
        r"\1[REDACTED: generic_secret_assignment]"
    ),
    ("pan_number", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"), "[REDACTED: pan_number]"),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED: ssn]"),
    ("credit_card", re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "luhn_callback"),
    ("aadhaar_number", re.compile(r"(?<!\d\s)(?<!\d-)(?<!\d)[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}(?![\s-]?\d)"), "[REDACTED: aadhaar_number]"),
    ("phone_number", re.compile(r"\b(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}\b"), "[REDACTED: phone_number]"),
    ("ip_address", re.compile(r"\b(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}\b"), "ip_callback"),
    (
        "crypto_wallet",
        re.compile(r"\b(?:0x[a-fA-F0-9]{40}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{39,59})\b"),
        "[REDACTED: crypto_wallet]"
    ),
]

def normalize_with_mapping(text: str) -> Tuple[str, List[int]]:
    norm_chars = []
    norm_to_orig = []
    i = 0
    n = len(text)
    while i < n:
        char = text[i]
        if char in (' ', '\t'):
            prev_char = text[i-1] if i > 0 else ''
            j = i + 1
            while j < n and text[j] in (' ', '\t'):
                j += 1
            next_char = text[j] if j < n else ''

            if prev_char in ('-', '_', ':', '=') or (prev_char.isalnum() and next_char.isalnum()):
                i += 1
                continue

        norm_chars.append(char)
        norm_to_orig.append(i)
        i += 1

    return "".join(norm_chars), norm_to_orig

def get_match_spans(text: str) -> List[dict]:
    spans = []
    norm_text, norm_map = normalize_with_mapping(text)

    for item in PATTERNS:
        reason = item[0]
        pattern = item[1]
        replacement = item[2] if len(item) > 2 else f"[REDACTED: {reason}]"

        matches_orig = list(pattern.finditer(text))
        matches_norm = list(pattern.finditer(norm_text)) if norm_map else []

        found_matches = []
        for match in matches_orig:
            found_matches.append((match.start(), match.end(), match.group(0)))

        for match in matches_norm:
            if not norm_map or match.start() >= len(norm_map):
                continue
            orig_start = norm_map[match.start()]
            orig_end_idx = match.end() - 1
            if orig_end_idx >= len(norm_map):
                orig_end = len(text)
            else:
                orig_end = norm_map[orig_end_idx] + 1
            matched_str = text[orig_start:orig_end]

            if not any(abs(m[0] - orig_start) <= 2 and abs(m[1] - orig_end) <= 2 for m in found_matches):
                found_matches.append((orig_start, orig_end, matched_str))

        for m_start, m_end, matched_str in found_matches:
            if replacement == "luhn_callback":
                if is_luhn_valid(matched_str):
                    spans.append({"start": m_start, "end": m_end, "reason": "credit_card", "severity": "redact"})
            elif replacement == "ip_callback":
                tag = classify_ip(matched_str)
                if tag:
                    spans.append({"start": m_start, "end": m_end, "reason": tag, "severity": "redact"})
            elif reason == "generic_secret_assignment":
                spans.append({"start": m_start, "end": m_end, "reason": reason, "severity": "redact"})
            else:
                sev = get_severity(reason, matched_str)
                spans.append({"start": m_start, "end": m_end, "reason": reason, "severity": sev})
    return spans

def scan_and_redact(text: str) -> Tuple[str, bool, List[str], List[dict]]:
    """
    Scans text for sensitive patterns and secrets (supporting optional whitespace in key runs).
    Replaces matched spans with '[REDACTED: reason]'.
    Returns (redacted_text, has_secrets, reasons, match_spans).
    """
    spans = get_match_spans(text)
    if not spans:
        return text, False, [], []

    # Deduplicate spans
    unique_spans = []
    for s in sorted(spans, key=lambda x: (x["start"], -x["end"])):
        if not any(u["start"] <= s["start"] and u["end"] >= s["end"] for u in unique_spans):
            unique_spans.append(s)

    found_reasons = []
    redacted_text = text

    # Apply redactions right-to-left
    for s in sorted(unique_spans, key=lambda x: x["start"], reverse=True):
        reason = s["reason"]
        if reason not in found_reasons:
            found_reasons.insert(0, reason)
        repl = f"[REDACTED: {reason}]"
        redacted_text = redacted_text[:s["start"]] + repl + redacted_text[s["end"]:]

    has_secrets = len(found_reasons) > 0
    return redacted_text, has_secrets, found_reasons, unique_spans
