import sys
import json
from datetime import datetime, timezone
from pathlib import Path

# Add parent backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pattern_detector import scan_and_redact
from corpus import most_similar

RESULTS_FILE = Path(__file__).parent.parent / "coverage_results.json"

TEST_CASES = [
    {
        "id": 1,
        "name": "Secret with inserted whitespace",
        "input": "The secret API key is sk- 123456789012345678901234",
    },
    {
        "id": 2,
        "name": "Secret described in prose",
        "input": "The database password is Winter2026Secure for production",
    },
    {
        "id": 3,
        "name": "Base64-encoded key snippet",
        "input": "Encoded token: c2stMTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0",
    },
    {
        "id": 4,
        "name": "Leetspeak password substitution",
        "input": "Admin credentials: P4ssw0rd!123 for root user",
    },
    {
        "id": 5,
        "name": "Paraphrased corpus sentence",
        "input": "The executive board authorized proceeding with buying Northwind Analytics for a total price of approximately 42 million dollars.",
    },
    {
        "id": 6,
        "name": "Secret split across two sentences",
        "input": "Our key starts with sk-proj-8fJ2... and continues kLmN9pQrStUv...",
    },
]

def save_coverage_results(redteam_data):
    data = {}
    if RESULTS_FILE.exists():
        try:
            data = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    data["redteam"] = redteam_data

    # Generate summary line
    redteam_hits = redteam_data.get("redacted", 0) + redteam_data.get("blocked", 0)
    redteam_total = redteam_data.get("total", 6)
    
    benign_data = data.get("benign", {})
    benign_passed = benign_data.get("passed", 0)
    benign_total = benign_data.get("total", 0)

    if benign_total > 0:
        summary_line = f"Catches {redteam_hits}/{redteam_total} obfuscation techniques via layers; {benign_passed}/{benign_total} benign prompts correctly allowed."
    else:
        summary_line = f"Catches {redteam_hits}/{redteam_total} obfuscation techniques via layers."

    data["summary_line"] = summary_line
    RESULTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def run_redteam_tests():
    print("\n" + "=" * 95)
    print("                RED TEAM OBFUSCATED SECRET & LEAK DETECTION TEST REPORT")
    print("=" * 95)
    print(f"{'ID':<4} | {'Test Case':<36} | {'Regex':<8} | {'Semantic':<10} | {'Action':<8} | {'Detail':<18}")
    print("-" * 95)

    regex_caught = 0
    semantic_caught = 0
    blocked_count = 0
    redacted_count = 0
    allowed_count = 0
    cases_result = []

    for tc in TEST_CASES:
        text = tc["input"]
        
        # 1. Regex check
        redacted_text, has_secrets, secret_reasons, raw_matches = scan_and_redact(text)
        regex_hit = "HIT" if has_secrets else "MISS"
        if has_secrets:
            regex_caught += 1

        # 2. Semantic check
        doc_name, score = most_similar(text)
        is_semantic_hit = score > 0.45
        semantic_hit = "HIT" if is_semantic_hit else "MISS"
        if is_semantic_hit:
            semantic_caught += 1

        # 3. Overall action determination
        has_block = any(m.get("severity") == "block" for m in raw_matches)
        if has_block:
            action = "BLOCK"
            blocked_count += 1
        elif has_secrets or is_semantic_hit:
            action = "REDACT"
            redacted_count += 1
        else:
            action = "ALLOW"
            allowed_count += 1

        detail = ""
        if has_secrets:
            detail = ", ".join(secret_reasons)
        if is_semantic_hit:
            sim_pct = int(score * 100)
            detail += f" ({sim_pct}% {doc_name})" if detail else f"{sim_pct}% {doc_name}"
        if not detail:
            detail = "No match"

        cases_result.append({
            "id": tc["id"],
            "name": tc["name"],
            "regex": regex_hit,
            "semantic": semantic_hit,
            "action": action,
            "detail": detail
        })

        print(f"{tc['id']:<4} | {tc['name']:<36} | {regex_hit:<8} | {semantic_hit:<10} | {action:<8} | {detail[:18]:<18}")

    print("-" * 95)
    print("SUMMARY AUDIT STATS:")
    print(f"  Total Probe Cases      : {len(TEST_CASES)}")
    print(f"  Regex Layer Hits       : {regex_caught}/{len(TEST_CASES)}")
    print(f"  Semantic Layer Hits    : {semantic_caught}/{len(TEST_CASES)}")
    print(f"  Final Actions Breakdown: BLOCK={blocked_count}, REDACT={redacted_count}, ALLOW={allowed_count}")
    print("=" * 95 + "\n")

    save_coverage_results({
        "total": len(TEST_CASES),
        "regex_hits": regex_caught,
        "semantic_hits": semantic_caught,
        "blocked": blocked_count,
        "redacted": redacted_count,
        "allowed": allowed_count,
        "cases": cases_result
    })

if __name__ == "__main__":
    run_redteam_tests()
