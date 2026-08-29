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

def get_match_spans(text: str) -> List[dict]:
    spans = []
    for item in PATTERNS:
        reason = item[0]
        pattern = item[1]
        replacement = item[2] if len(item) > 2 else f"[REDACTED: {reason}]"

        for match in pattern.finditer(text):
            m_start, m_end = match.start(), match.end()
            if replacement == "luhn_callback":
                if is_luhn_valid(match.group(0)):
                    spans.append({"start": m_start, "end": m_end, "reason": "credit_card"})
            elif replacement == "ip_callback":
                tag = classify_ip(match.group(0))
                if tag:
                    spans.append({"start": m_start, "end": m_end, "reason": tag})
            elif reason == "generic_secret_assignment":
                if len(match.groups()) >= 2 and match.start(2) != -1:
                    spans.append({"start": match.start(2), "end": match.end(2), "reason": reason})
                else:
                    spans.append({"start": m_start, "end": m_end, "reason": reason})
            else:
                spans.append({"start": m_start, "end": m_end, "reason": reason})
    return spans

def scan_and_redact(text: str) -> Tuple[str, bool, List[str], List[dict]]:
    """
    Scans text for sensitive patterns and secrets.
    Replaces matched spans with '[REDACTED: reason]'.
    Returns (redacted_text, has_secrets, reasons, match_spans).
    """
    redacted_text = text
    found_reasons = []
    spans = get_match_spans(text)

    for item in PATTERNS:
        reason = item[0]
        pattern = item[1]
        replacement = item[2] if len(item) > 2 else f"[REDACTED: {reason}]"

        if replacement == "luhn_callback":
            matches_found = False
            def _card_sub(match):
                nonlocal matches_found
                val = match.group(0)
                if is_luhn_valid(val):
                    matches_found = True
                    return "[REDACTED: credit_card]"
                return val

            new_text = pattern.sub(_card_sub, redacted_text)
            if matches_found:
                if reason not in found_reasons:
                    found_reasons.append(reason)
                redacted_text = new_text

        elif replacement == "ip_callback":
            sub_reasons = []
            def _ip_sub(match):
                val = match.group(0)
                tag = classify_ip(val)
                if tag:
                    if tag not in sub_reasons:
                        sub_reasons.append(tag)
                    return f"[REDACTED: {tag}]"
                return val

            redacted_text = pattern.sub(_ip_sub, redacted_text)
            for r in sub_reasons:
                if r not in found_reasons:
                    found_reasons.append(r)

        else:
            matches = list(pattern.finditer(redacted_text))
            if matches:
                if reason not in found_reasons:
                    found_reasons.append(reason)
                redacted_text = pattern.sub(replacement, redacted_text)

    has_secrets = len(found_reasons) > 0
    return redacted_text, has_secrets, found_reasons, spans
