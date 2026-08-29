# Redactor - Semantic AI Leak Detection & Security Tool

Redactor is a privacy and data-loss prevention (DLP) tool designed to prevent sensitive company information, credentials, and PII from being leaked into public AI models (such as ChatGPT).

It acts as a real-time local security guard, running both **deep pattern detection (regex + Luhn algorithm)** and **local semantic vector similarity checks** right before prompts leave your browser.

---

##  Key Features

- **Chrome Extension (MV3)**:
  - Hooks directly into ChatGPT prompt boxes (`chatgpt.com`).
  - **Live Typing Risk Indicator**: Shows a real-time status badge (🟢 Clear, 🟡 Sensitive content detected, 🔴 Will be blocked) debounced ~600ms while you type.
  - **Live Inline Preview Overlay**: Highlights sensitive matches inline over the prompt box in real-time.
  - **Auto-Redaction & Blocking**: Replaces sensitive spans with `[REDACTED: reason]` before sending, or blocks critical prompts completely.

- **Deep Pattern Detection Engine (13 Categories)**:
  - **API Keys**: OpenAI-style keys (`sk-...`).
  - **Database Connection Strings**: Redacts credentials in `postgresql://`, `mysql://`, `mongodb://`, `redis://`, etc.
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

- **Live Monitoring Dashboard & Audit Logging**:
  - Dark-themed live dashboard served at `http://localhost:8000/`.
  - Auto-refreshes every 5 seconds to display real-time prompt check activity.
  - SQLite audit log (`backend/logs.db`) capturing length, action, reason, matched doc, and timestamp.

---

##  Project Architecture

```
Redactor/
├── backend/                  # FastAPI Python Service
│   ├── main.py               # REST API (/check, /logs, Live Dashboard /)
│   ├── pattern_detector.py   # Regex & Luhn validation engine
│   ├── corpus.py             # SentenceTransformer vector embedding & cosine check
│   ├── db.py                 # SQLite audit logger (logs.db)
│   ├── test_pattern_detector.py # Unit test suite
│   └── requirements.txt      # Python dependencies
├── corpus/                   # Confidential reference document corpus (.txt)
├── extension/                # Chrome MV3 Content Extension
│   ├── manifest.json         # Extension configuration
│   ├── content.js            # Interception, typing preview overlay, toast notifications
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

To run the standalone unit test suite for the pattern detector:

```bash
python backend/test_pattern_detector.py
```

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
