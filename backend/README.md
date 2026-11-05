# Redactor Backend

FastAPI backend service for Redactor.

## Requirements

- Python 3.8+

## Setup & Run
## Semantic Detection

The backend loads `all-MiniLM-L6-v2` once at startup and caches normalized embeddings for each sentence in the confidential `.txt` corpus. New prompts are embedded per request and compared in a vectorized cosine-similarity operation. A matching prompt sentence is redacted while unrelated text is preserved.

The semantic match cutoff defaults to `0.60` and can be overridden before starting the backend:

```powershell
$env:REDACTOR_SEMANTIC_THRESHOLD = "0.60"
```

The corpus directory defaults to the repository's `corpus` folder. To point at a different directory of confidential `.txt` references:

```powershell
$env:REDACTOR_CORPUS_DIR = "C:\path\to\confidential-corpus"
```

Tune the cutoff against representative positive and harmless negative examples for your organization; similarity is a signal for review/redaction, not proof of disclosure. `0.60` is calibrated against the repository's current Falcon paraphrases and negative controls, not a universal model guarantee.

## Local Policy

Edit `backend/policy.json` to configure the default action, semantic action, or individual category actions. Supported actions are `allow`, `redact`, and `block`. Severity-level mandatory detections such as SSNs, Aadhaar numbers, and private-key blocks cannot be downgraded by policy. Restart the backend after editing the file.

Set `REDACTOR_POLICY_PATH` to use a policy file outside the repository. The active settings are visible at `http://127.0.0.1:8000/policy`; `http://127.0.0.1:8000/health` reports model and corpus readiness without exposing corpus contents.

## Setup & Run

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```

2. (Optional) Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Start the uvicorn server:
   ```bash
   uvicorn main:app --reload
   ```

The API will be available at `http://127.0.0.1:8000`. You can test the endpoints via interactive API docs at `http://127.0.0.1:8000/docs`.
