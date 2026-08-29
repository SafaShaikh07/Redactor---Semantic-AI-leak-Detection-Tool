import sys
import json
from datetime import datetime, timezone
from pathlib import Path

# Add parent backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pattern_detector import scan_and_redact
from corpus import most_similar

RESULTS_FILE = Path(__file__).parent.parent / "coverage_results.json"

BENIGN_PROMPTS = [
    "What is the key difference between a list and a tuple in Python?",
    "How do I reset my user password conceptually in a Web application?",
    "Can you explain how a public/private key pair works in RSA cryptography?",
    "Write a Python function to sort a list of dictionaries by a specific key name.",
    "What are the best practices for designing a secure API token authentication flow?",
    "How do I calculate compound interest in Excel?",
    "Explain the concept of key-value stores in database systems.",
    "What is the difference between primary key and foreign key in SQL?",
    "Can you give me a summary of the French Revolution?",
    "How do I fix a NullPointerException in Java?",
    "Write a polite email asking for an extension on a project deadline.",
    "Invalid card number test string 1234 5678 9012 3456 that fails Luhn validation.",
    "In the year 2026, our team completed 5000 tasks and processed 123 items.",
    "How does a hash map resolve collisions using chaining?",
    "Explain the difference between authentication and authorization.",
    "What is a secret sharing scheme like Shamir's Secret Sharing?",
    "How do I configure CORS headers in FastAPI?",
    "Write a CSS grid layout with 3 columns and 20px gap.",
    "What are the primary colors in additive color mixing?",
    "How do I convert a string to uppercase in JavaScript?",
    "Explain how garbage collection works in Python.",
    "What is the capital city of Australia?",
    "Write a unit test using pytest for a math function.",
    "What is the purpose of the virtual DOM in React?",
    "How do I read a CSV file using pandas in Python?",
    "Can you explain recursion using the Fibonacci sequence as an example?",
    "What is the difference between HTTP and HTTPS?",
    "Write a regex to match alphanumeric strings with 5 to 10 characters."
]

def save_coverage_results(benign_data):
    data = {}
    if RESULTS_FILE.exists():
        try:
            data = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    data["benign"] = benign_data

    # Generate summary line
    redteam_data = data.get("redteam", {})
    redteam_hits = redteam_data.get("redacted", 0) + redteam_data.get("blocked", 0)
    redteam_total = redteam_data.get("total", 6)

    benign_passed = benign_data.get("passed", 0)
    benign_total = benign_data.get("total", 28)

    summary_line = f"Catches {redteam_hits}/{redteam_total} obfuscation techniques via layers; {benign_passed}/{benign_total} benign prompts correctly allowed."
    data["summary_line"] = summary_line

    RESULTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def run_benign_tests():
    print("\n" + "=" * 95)
    print("                BENIGN PROMPT BASELINE FALSE-POSITIVE TEST REPORT")
    print("=" * 95)
    print(f"{'ID':<4} | {'Prompt Snippet':<45} | {'Regex':<8} | {'Semantic':<10} | {'Action':<8}")
    print("-" * 95)

    passed_count = 0
    false_positives = []

    for i, text in enumerate(BENIGN_PROMPTS, 1):
        # 1. Regex check
        redacted_text, has_secrets, secret_reasons, raw_matches = scan_and_redact(text)
        regex_hit = "HIT" if has_secrets else "MISS"

        # 2. Semantic check
        doc_name, score = most_similar(text)
        is_semantic_hit = score > 0.45
        semantic_hit = "HIT" if is_semantic_hit else "MISS"

        # 3. Overall action determination
        has_block = any(m.get("severity") == "block" for m in raw_matches)
        if has_block:
            action = "BLOCK"
        elif has_secrets or is_semantic_hit:
            action = "REDACT"
        else:
            action = "ALLOW"

        if action == "ALLOW":
            passed_count += 1
        else:
            reasons_matched = secret_reasons.copy()
            if is_semantic_hit:
                reasons_matched.append(f"semantic ({doc_name}: {score:.2f})")
            false_positives.append({
                "id": i,
                "text": text,
                "action": action,
                "reasons": reasons_matched
            })

        snippet = text if len(text) <= 45 else text[:42] + "..."
        print(f"{i:<4} | {snippet:<45} | {regex_hit:<8} | {semantic_hit:<10} | {action:<8}")

    print("-" * 95)
    print("SUMMARY BASELINE STATS:")
    print(f"  Total Benign Prompts Tested : {len(BENIGN_PROMPTS)}")
    print(f"  Correctly Allowed (Pass)    : {passed_count}/{len(BENIGN_PROMPTS)} ({passed_count/len(BENIGN_PROMPTS)*100:.1f}%)")
    print(f"  False Positives             : {len(false_positives)}")

    if false_positives:
        print("\nFALSE POSITIVES BREAKDOWN:")
        for fp in false_positives:
            print(f"  - Prompt #{fp['id']}: \"{fp['text']}\"")
            print(f"    Action: {fp['action']}, Flagged as: {', '.join(fp['reasons'])}\n")
    else:
        print("  False Positives Breakdown   : None (0 false positives)")

    print("=" * 95 + "\n")

    save_coverage_results({
        "total": len(BENIGN_PROMPTS),
        "passed": passed_count,
        "false_positives_count": len(false_positives),
        "false_positives": false_positives
    })

if __name__ == "__main__":
    run_benign_tests()
