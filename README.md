# Redactor - Semantic AI Leak Detection & Security Tool

Redactor is a privacy and data-loss prevention (DLP) tool designed to prevent sensitive company information, credentials, and PII from being leaked into public AI models (such as ChatGPT).

It acts as a real-time local security guard, running both **deep pattern detection (regex + Luhn algorithm + whitespace normalization)** and **local semantic vector similarity checks** right before prompts leave your browser.

---

##  Key Features

- **Chrome Extension (MV3)**:
  - Hooks directly into ChatGPT prompt boxes (`chatgpt.com`).
  - **Live Typing Risk Indicator**: Shows a real-time coloured status badge (Clear, Sensitive content detected Will be blocked) debounced ~600ms while you type with interactive hover explanations.
  - **Live Inline Preview Overlay**: Highlights sensitive matches inline over the prompt box in real-time.
  - **Auto-Redaction & Blocking**: Replaces sensitive spans with `[REDACTED: reason]` before sending, or blocks critical prompts completely.

- **Two-Tier Severity & Decision Logic**:
  - **BLOCK-Level (Action: `block`)**: Refuses to send any version of the prompt if critical data is detected (Private Keys, SSN, Indian Aadhaar, Database URIs containing passwords).
  - **REDACT-Level (Action: `redact`)**: Strips the sensitive span and allows the cleaned prompt through (API Keys, Email, Phone Numbers, PAN Numbers, Credit Cards, IP Addresses, Crypto Wallets, Generic Secret Assignments, Project Codenames).
  - **Priority Logic**: Any `BLOCK`-level match triggers a prompt block regardless of other matches.

- **Deep Pattern Detection Engine (13 Categories + Whitespace Normalization)**:
  - **API Keys**: OpenAI-style keys (`sk-...`) with internal whitespace tolerance (`sk- abc123...`).
  - **Database Connection Strings**: Redacts credentials in `postgresql://`, `mysql://`, `mongodb://`, `redis://`, etc., elevating to `BLOCK` when passwords are included.
  - **Private Keys**: PEM-format private key blocks (`-----BEGIN PRIVATE KEY-----`).
  - **Generic Secret Assignments**: Catch-all for `KEY=value` or `KEY: value` lines containing `SECRET`, `PASSWORD`, `TOKEN`, `API_KEY`, etc.
  - **Credit Cards**: Validates 13–19 digit card numbers using the **Luhn algorithm** to eliminate false positives.
  - **PII & Government IDs**: Indian PAN Cards, Indian Aadhaar Numbers, and US Social Security Numbers (SSN).
  - **Contact Info**: Emails and international phone numbers.
  - **IP Addresses**: Distinguishes between `ip_address:private` and `ip_address:public`.
  - **Crypto Wallets**: Bitcoin (`1...`, `3...`, `bc1...`) and Ethereum (`0x...`) addresses.
  - **Project Codenames**: Internal project names (`Project <Codename>`).

- **Semantic Vector Leak Detection**:
  - Embedded locally using `sentence-transformers` (`all-MiniLM-L6-v2`).
  - Vectorizes internal documents (`./corpus/*.txt`) at startup.
  - Flags prompts matching confidential docs with cosine similarity > **0.45**, catching paraphrased or reworded leaks.

- **Live Monitoring Dashboard, Metrics & Audit Logging**:
  - **Stats Bar**: Displays total checks, block rate %, redact rate %, and average latency (ms).
  - **Live Protection Log**: Dark-themed table served at `http://localhost:8000/` auto-refreshed every 5 seconds.
  - **Interactive Tooltips**: Hovering over any `REASON` cell shows character span lengths for patterns or percentage match scores + document names for semantic matches.
  - **Collapsible Detection Coverage Report**: Renders persisted audit results from red-team obfuscation probes and benign prompt false-positive benchmarks (`GET /coverage`).
  - **SQLite Audit Log**: Backward-compatible SQLite database (`backend/logs.db`) storing length, action, reason, matched doc, reason details, latency (ms), and ISO8601 UTC timestamp.

---

##  Project Architecture

```
Redactor/
├── backend/                  # FastAPI Python Service
│   ├── main.py               # REST API (/check, /logs, /metrics, /coverage, Dashboard /)
│   ├── pattern_detector.py   # Regex, Luhn validation & whitespace normalization engine
│   ├── corpus.py             # SentenceTransformer vector embedding & cosine check
│   ├── db.py                 # SQLite audit logger & aggregate metrics engine (logs.db)
│   ├── coverage_results.json # Persisted test suite benchmarks & coverage data
│   ├── test_pattern_detector.py # Pattern unit test suite
│   ├── tests/
│   │   ├── test_redteam.py   # Red team obfuscated secret probe suite
│   │   └── test_benign.py    # Benign prompt false-positive benchmark suite
│   └── requirements.txt      # Python dependencies
├── corpus/                   # Confidential reference document corpus (.txt)
├── extension/                # Chrome MV3 Content Extension
│   ├── manifest.json         # Extension configuration
│   ├── content.js            # Interception, typing preview overlay, risk badge, toasts
│   └── README.md             # Extension installation guide
└── README.md                 # Project Overview & Setup Guide
```

---

##  Getting Started

### 1. Prerequisites
- **Python**: Version 3.8 or higher.
- **Google Chrome**: For running the unpacked extension.

### 2. Set Up & Run the Backend

```bash
# 1. Navigate to the backend directory
cd backend

# 2. (Optional) Create and activate a virtual environment
python -m venv venv
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the server
uvicorn main:app --reload
```

The API and Live Dashboard will be available at:
- **Live Dashboard**: [http://localhost:8000/](http://localhost:8000/)
- **API Endpoint**: `POST http://localhost:8000/check`
- **Metrics API**: `GET http://localhost:8000/metrics`
- **Coverage API**: `GET http://localhost:8000/coverage`
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 3. Load the Chrome Extension

1. Open Google Chrome and go to `chrome://extensions/`.
2. Toggle on **Developer mode** in the top-right corner.
3. Click **Load unpacked** in the top-left menu.
4. Select the `./extension` folder from this repository.
5. Open [https://chatgpt.com/](https://chatgpt.com/) and start typing!

---

##  Running Tests

Redactor includes three test suites for verifying pattern accuracy, red-team obfuscation detection, and benign prompt false-positive rates:

```bash
# 1. Run pattern detector unit tests
python backend/test_pattern_detector.py

# 2. Run red-team obfuscation probe suite (updates coverage_results.json)
python backend/tests/test_redteam.py

# 3. Run benign prompt false-positive benchmark suite (updates coverage_results.json)
python backend/tests/test_benign.py
```

---

##  License

This project is open-source and available under the [MIT License](LICENSE).
