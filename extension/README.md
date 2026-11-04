# Redactor Chrome Extension (MV3)

A Manifest V3 extension that intercepts ChatGPT prompts, checks them against the Redactor backend at `http://localhost:8000/check`, and automatically redacts or blocks sensitive content.

## Features

- **Prompt Interception**: Hooks into ChatGPT's prompt textarea and send button.
- **Live risk status**: Shows when a prompt is being checked, clear, sensitive, blocked, rate-limited, or unable to reach the backend. Stale results from earlier text are ignored.
- **Request timeout**: Backend checks time out instead of leaving the status on "Checking..." indefinitely.
- **Backend Check**: The content script sends prompt text through the Manifest V3 service worker to `http://localhost:8000/check`, using the extension's localhost host permission.
- **Actions**:
  - `allow`: Submits prompt normally.
  - `redact`: Replaces text with redacted version, displays dark-themed toast notification ("Redacted before sending"), and submits after a brief delay.
  - `block`: Prevents submission entirely and displays a notification with the reason.
- **Fail-closed behavior**: If the backend is offline, rate-limited, or returns an invalid response, the extension keeps the prompt in the composer and does not send it. Start or restore the backend, then retry.

## How to Load as Unpacked Extension in Chrome

1. Open Google Chrome.
2. Navigate to `chrome://extensions/` in the address bar.
3. Turn on **Developer mode** using the toggle switch in the top-right corner.
4. Click the **Load unpacked** button in the top-left menu.
5. Select the `extension` directory from the repository root (`./extension`).
6. Ensure the Redactor FastAPI backend is running locally at `http://localhost:8000`.
7. Go to [https://chatgpt.com/](https://chatgpt.com/) and test entering prompts!
