/*
 * Redactor Extension - Content Script
 * 
 * HOW TO LOAD AS AN UNPACKED EXTENSION IN CHROME:
 * 1. Open Google Chrome and navigate to chrome://extensions/
 * 2. Enable "Developer mode" using the toggle in the top-right corner.
 * 3. Click the "Load unpacked" button in the top-left corner.
 * 4. Select the "extension" directory inside this project (e.g., ./redactor/extension).
 * 5. Open https://chatgpt.com/ - the extension is now active!
 */

(function () {
  'use strict';

  let isBypassingCheck = false;
  let rateLimitUntil = 0;
  const PROVIDERS = [
    {
      host: 'chatgpt.com',
      promptSelectors: ['#prompt-textarea', '[data-testid="composer-text-input"]', 'textarea[placeholder*="Message"]', 'div[contenteditable="true"]'],
      sendSelectors: ['button[data-testid="send-button"]', 'button[aria-label*="Send"]', 'form button[type="submit"]']
    },
    {
      host: 'claude.ai',
      promptSelectors: ['div.ProseMirror[contenteditable="true"]', '[contenteditable="true"][data-placeholder]', 'div[contenteditable="true"]', 'textarea'],
      sendSelectors: ['button[aria-label*="Send message"]', 'button[aria-label*="Send"]', 'form button[type="submit"]']
    },
    {
      host: 'gemini.google.com',
      promptSelectors: ['rich-textarea .ql-editor[contenteditable="true"]', '.ql-editor[contenteditable="true"]', 'div[contenteditable="true"][aria-label]', 'textarea'],
      sendSelectors: ['button.send-button', 'button[aria-label*="Send"]', 'form button[type="submit"]']
    },
    {
      host: 'copilot.microsoft.com',
      promptSelectors: ['textarea#userInput', 'textarea[placeholder*="Ask"]', '[contenteditable="true"][role="textbox"]', 'div[contenteditable="true"]'],
      sendSelectors: ['button[aria-label*="Submit"]', 'button[data-testid*="send"]', 'button[aria-label*="Send"]', 'form button[type="submit"]']
    }
  ];

  function getActiveProvider() {
    return PROVIDERS.find(provider =>
      window.location.hostname === provider.host || window.location.hostname.endsWith(`.${provider.host}`)
    ) || PROVIDERS[0];
  }

  function findVisibleElement(selectors) {
    for (const selector of selectors) {
      for (const element of document.querySelectorAll(selector)) {
        if (element.getClientRects().length && !element.disabled) return element;
      }
    }
    return null;
  }

  function requestCheck(text) {
    return new Promise((resolve, reject) => {
      if (typeof chrome === 'undefined' || !chrome.runtime || !chrome.runtime.sendMessage) {
        const error = new Error('Redactor extension context is unavailable. Reload the extension and refresh this tab.');
        error.code = 'EXTENSION_CONTEXT_UNAVAILABLE';
        reject(error);
        return;
      }

      let settled = false;
      const timeoutId = setTimeout(() => {
        if (settled) return;
        settled = true;
        const error = new Error('Redactor extension did not respond in time. Reload the extension and refresh this tab.');
        error.code = 'EXTENSION_RESPONSE_TIMEOUT';
        reject(error);
      }, 12000);

      try {
        chrome.runtime.sendMessage({ type: 'redactor-check', text }, response => {
          if (settled) return;
          settled = true;
          clearTimeout(timeoutId);
          if (chrome.runtime.lastError) {
            const error = new Error(chrome.runtime.lastError.message);
            error.code = 'EXTENSION_CONTEXT_UNAVAILABLE';
            reject(error);
          } else if (!response) {
            reject(new Error('Redactor backend returned no response.'));
          } else {
            resolve(response);
          }
        });
      } catch (error) {
        clearTimeout(timeoutId);
        error.code = 'EXTENSION_CONTEXT_UNAVAILABLE';
        reject(error);
      }
    });
  }

  async function parseRetryAfter(response) {
    const retryHeader = response.retryAfter;
    if (retryHeader) {
      const parsed = parseInt(retryHeader, 10);
      if (!isNaN(parsed) && parsed > 0) return parsed;
    }
    if (response.data && response.data.retry_after_seconds) {
      return response.data.retry_after_seconds;
    }
    return 2;
  }

  // Create toast element container
  function createToast(message, duration = 3000, isError = false) {
    let toast = document.getElementById('redactor-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'redactor-toast';
      toast.style.cssText = `
        position: fixed;
        bottom: 80px;
        right: 20px;
        z-index: 999999;
        background-color: #1e1e2e;
        color: #f5e0dc;
        padding: 12px 18px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: 14px;
        font-weight: 500;
        border-left: 4px solid #89b4fa;
        opacity: 0;
        transform: translateY(10px);
        transition: opacity 0.3s ease, transform 0.3s ease;
        pointer-events: none;
      `;
      document.body.appendChild(toast);
    }

    toast.style.borderLeftColor = isError ? '#f38ba8' : '#89b4fa';
    toast.textContent = message;

    // Trigger animation
    requestAnimationFrame(() => {
      toast.style.opacity = '1';
      toast.style.transform = 'translateY(0)';
    });

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
    }, duration);
  }

  // Get current text from ChatGPT prompt container
  function getPromptText(element) {
    if (!element) return '';
    if (element.tagName === 'TEXTAREA' || element.tagName === 'INPUT') {
      return element.value;
    }
    if (element.isContentEditable) {
      return element.innerText || element.textContent || '';
    }
    return '';
  }

  // Set prompt text properly so React updates state
  function setPromptText(element, text) {
    if (!element) return;
    if (element.tagName === 'TEXTAREA' || element.tagName === 'INPUT') {
      const prototype = Object.getPrototypeOf(element);
      const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
      const valueSetter = Object.getOwnPropertyDescriptor(element, 'value')?.set;
      
      if (prototypeValueSetter && valueSetter !== prototypeValueSetter) {
        prototypeValueSetter.call(element, text);
      } else if (valueSetter) {
        valueSetter.call(element, text);
      } else {
        element.value = text;
      }
    } else if (element.isContentEditable) {
      element.innerText = text;
    }

    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // Find ChatGPT prompt input element
  function findPromptElement() {
    return findVisibleElement(getActiveProvider().promptSelectors);
  }

  // Find ChatGPT send button
  function findSendButton() {
    return findVisibleElement(getActiveProvider().sendSelectors);
  }

  // Submit prompt programmatically
  function triggerSubmit(promptElement) {
    isBypassingCheck = true;
    const sendButton = findSendButton();
    if (sendButton) {
      sendButton.click();
    } else if (promptElement) {
      const enterEvent = new KeyboardEvent('keydown', {
        key: 'Enter',
        code: 'Enter',
        keyCode: 13,
        which: 13,
        bubbles: true,
        cancelable: true
      });
      promptElement.dispatchEvent(enterEvent);
    }
    setTimeout(() => {
      isBypassingCheck = false;
    }, 500);
  }

  function blockSubmission(promptElement, message, reasonDetail) {
    updateRiskIndicator('block', promptElement, reasonDetail || message);
    updateTextareaHighlights(promptElement, [], 'block');
    createToast(message, 5000, true);
  }

  // Core handler for checking prompt
  async function handleIntercept(e, promptElement) {
    if (isBypassingCheck) return;

    const text = getPromptText(promptElement).trim();
    if (!text) return;

    clearTimeout(debounceTimer);
    liveCheckRequestId++;
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    const maxRetries = 2;
    let response = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      if (Date.now() < rateLimitUntil) {
        const waitMs = Math.max(100, rateLimitUntil - Date.now());
        if (attempt === 0) {
          createToast('Rate limit active. Briefly pausing before check...', 2000, false);
        }
        await new Promise(resolve => setTimeout(resolve, waitMs));
      }

      try {
        response = await requestCheck(text);

        if (response.status === 429) {
          const retrySec = await parseRetryAfter(response);
          rateLimitUntil = Date.now() + (retrySec * 1000);
          if (attempt < maxRetries) {
            createToast(`Rate limit exceeded. Retrying check in ${retrySec}s...`, retrySec * 1000, false);
            await new Promise(resolve => setTimeout(resolve, retrySec * 1000 + 100));
            continue;
          }
        }

        break;
      } catch (err) {
        if (err && ['EXTENSION_CONTEXT_UNAVAILABLE', 'EXTENSION_RESPONSE_TIMEOUT'].includes(err.code)) {
          console.error('[Redactor] Extension messaging failed:', err);
          blockSubmission(promptElement, err.message);
          return;
        }
        if (attempt === maxRetries) {
          console.error('[Redactor] Error checking prompt:', err);
          blockSubmission(promptElement, 'Redactor backend unavailable. Prompt was not sent.');
          return;
        }
      }
    }

    if (!response || !response.ok) {
      if (response && response.status === 429) {
        blockSubmission(promptElement, 'Rate limit exceeded. Prompt was not sent; please wait and retry.');
        return;
      }
      if (response && response.status === 0) {
        blockSubmission(promptElement, response.error || 'Redactor backend unavailable. Prompt was not sent.');
        return;
      }
      const statusText = response ? ` (HTTP ${response.status})` : '';
      blockSubmission(promptElement, `Redactor check failed${statusText}. Prompt was not sent.`);
      return;
    }

    if (getPromptText(promptElement).trim() !== text) {
      console.info('[Redactor] Prompt changed during inspection; leaving the new text unsent.');
      return;
    }

    try {
      const data = response.data;

      if (data.action === 'allow') {
        updateRiskIndicator(null, promptElement);
        updateTextareaHighlights(promptElement, [], null);
        triggerSubmit(promptElement);
      } else if (data.action === 'redact') {
        if (typeof data.redacted_text !== 'string') {
          console.error('[Redactor] Redact response did not include redacted_text.');
          blockSubmission(promptElement, 'Redactor returned an invalid redaction. Prompt was not sent.');
          return;
        }
        setPromptText(promptElement, data.redacted_text);
        updateRiskIndicator(null, promptElement);
        updateTextareaHighlights(promptElement, [], null);
        createToast('Redacted before sending', 2500, false);
        setTimeout(() => {
          triggerSubmit(promptElement);
        }, 800);
      } else if (data.action === 'block') {
        updateRiskIndicator('block', promptElement, data.reason_detail);
        updateTextareaHighlights(promptElement, data.matches || [], 'block');
        const reasonMsg = data.reason ? `Blocked: ${data.reason}` : 'Prompt blocked by Redactor';
        createToast(reasonMsg, 4000, true);
      } else {
        console.error('[Redactor] Unexpected action in backend response:', data.action);
        blockSubmission(promptElement, 'Redactor returned an invalid decision. Prompt was not sent.');
      }
    } catch (err) {
      console.error('[Redactor] Error processing response:', err);
      blockSubmission(promptElement, 'Could not process Redactor response. Prompt was not sent.');
    }
  }

  function escapeHtml(str) {
    return (str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  let highlightedPromptElement = null;

  // Live inline overlay preview for matched redaction spans
  function updateTextareaHighlights(promptElement, matches, action) {
    let backdrop = document.getElementById('redactor-textarea-backdrop');

    if (!promptElement || !matches || matches.length === 0) {
      if (backdrop) backdrop.style.display = 'none';
      highlightedPromptElement = null;
      return;
    }

    const text = getPromptText(promptElement);
    if (!text) {
      if (backdrop) backdrop.style.display = 'none';
      highlightedPromptElement = null;
      return;
    }

    highlightedPromptElement = promptElement;

    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.id = 'redactor-textarea-backdrop';
      document.body.appendChild(backdrop);
    }

    const rect = promptElement.getBoundingClientRect();
    const style = window.getComputedStyle(promptElement);

    backdrop.style.cssText = `
      position: fixed;
      top: ${rect.top}px;
      left: ${rect.left}px;
      width: ${rect.width}px;
      height: ${rect.height}px;
      padding: ${style.padding};
      border: ${style.border};
      margin: 0;
      box-sizing: border-box;
      font-family: ${style.fontFamily};
      font-size: ${style.fontSize};
      font-weight: ${style.fontWeight};
      line-height: ${style.lineHeight};
      letter-spacing: ${style.letterSpacing};
      text-align: ${style.textAlign};
      white-space: pre-wrap;
      word-wrap: break-word;
      word-break: break-word;
      color: transparent;
      background: transparent;
      pointer-events: none;
      z-index: 2147483646;
      overflow: hidden;
      display: block;
    `;
    backdrop.scrollTop = promptElement.scrollTop || 0;
    backdrop.scrollLeft = promptElement.scrollLeft || 0;

    const sortedMatches = matches.slice().sort((a, b) => a.start - b.start);
    let html = '';
    let currentIndex = 0;

    for (const m of sortedMatches) {
      if (m.start < currentIndex) continue; // handle overlapping matches
      const before = text.slice(currentIndex, m.start);
      const matchedText = text.slice(m.start, m.end);

      const isBlock = m.severity === 'block' || action === 'block';
      const bg = isBlock ? 'rgba(244, 67, 54, 0.35)' : 'rgba(255, 193, 7, 0.35)';
      const border = isBlock ? '#f44336' : '#ffc107';

      html += escapeHtml(before);
      html += `<span style="background-color: ${bg}; border-bottom: 2px solid ${border}; border-radius: 2px; color: transparent;">${escapeHtml(matchedText)}</span>`;
      currentIndex = m.end;
    }
    html += escapeHtml(text.slice(currentIndex));

    backdrop.innerHTML = html;
  }

  function repositionTextareaHighlight() {
    const backdrop = document.getElementById('redactor-textarea-backdrop');
    if (!backdrop || !highlightedPromptElement) return;
    if (!document.contains(highlightedPromptElement)) {
      backdrop.style.display = 'none';
      highlightedPromptElement = null;
      return;
    }

    const rect = highlightedPromptElement.getBoundingClientRect();
    backdrop.style.top = `${rect.top}px`;
    backdrop.style.left = `${rect.left}px`;
    backdrop.style.width = `${rect.width}px`;
    backdrop.style.height = `${rect.height}px`;
    backdrop.scrollTop = highlightedPromptElement.scrollTop || 0;
    backdrop.scrollLeft = highlightedPromptElement.scrollLeft || 0;
  }

  document.addEventListener('scroll', repositionTextareaHighlight, true);
  window.addEventListener('resize', repositionTextareaHighlight);

  // Update persistent risk indicator in bottom corner of textarea
  function updateRiskIndicator(action, promptElement, reasonDetail) {
    let indicator = document.getElementById('redactor-risk-indicator');
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.id = 'redactor-risk-indicator';
      indicator.style.cssText = `
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 8px;
        border-radius: 12px;
        background-color: #181825;
        color: #cdd6f4;
        font-size: 11px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-weight: 500;
        position: absolute;
        bottom: 10px;
        right: 50px;
        z-index: 9999;
        box-shadow: 0 2px 6px rgba(0,0,0,0.25);
        transition: all 0.2s ease;
        pointer-events: auto;
        cursor: help;
      `;
    }

    if (promptElement) {
      const parent = promptElement.closest('form') || promptElement.parentElement;
      if (parent) {
        const computedStyle = window.getComputedStyle(parent);
        if (computedStyle.position === 'static') {
          parent.style.position = 'relative';
        }
        if (!parent.contains(indicator)) {
          parent.appendChild(indicator);
        }
      }
    }

    if (!action) {
      indicator.style.display = 'none';
      return;
    }

    indicator.style.display = 'inline-flex';

    let dotColor = '#4caf50';
    let labelText = 'Clear';

    if (action === 'allow') {
      dotColor = '#4caf50';
      labelText = 'Clear';
    } else if (action === 'redact') {
      dotColor = '#ff9800';
      labelText = 'Sensitive content detected';
    } else if (action === 'block') {
      dotColor = '#f44336';
      labelText = 'Will be blocked';
    } else if (action === 'checking') {
      dotColor = '#89b4fa';
      labelText = 'Checking...';
    } else if (action === 'rate_limited') {
      dotColor = '#ff9800';
      labelText = 'Check rate limited';
    } else if (action === 'unavailable') {
      dotColor = '#f44336';
      labelText = 'Check unavailable';
    }

    indicator.title = reasonDetail || labelText;
    indicator.innerHTML = `<span style="width:7px; height:7px; border-radius:50%; background-color:${dotColor}; display:inline-block;"></span><span>${labelText}</span>`;
  }

  // Debounced live risk check on typing
  let debounceTimer = null;
  let liveCheckRequestId = 0;

  function onPromptInput(e, delay = 600) {
    clearTimeout(debounceTimer);
    const requestId = ++liveCheckRequestId;
    const promptElement = findPromptElement();
    if (!promptElement) return;

    const text = getPromptText(promptElement).trim();
    if (!text) {
      updateRiskIndicator(null, promptElement);
      updateTextareaHighlights(promptElement, [], null);
      return;
    }

    if (Date.now() < rateLimitUntil) {
      updateRiskIndicator('rate_limited', promptElement);
      return;
    }

    updateRiskIndicator('checking', promptElement);
    debounceTimer = setTimeout(async () => {
      if (requestId !== liveCheckRequestId || getPromptText(promptElement).trim() !== text) return;
      if (Date.now() < rateLimitUntil) {
        updateRiskIndicator('rate_limited', promptElement);
        return;
      }

      try {
        const response = await requestCheck(text);
        if (response.status === 429) {
          const retrySec = await parseRetryAfter(response);
          rateLimitUntil = Date.now() + (retrySec * 1000);
          console.warn(`[Redactor] 429 Rate limit hit on typing check. Pausing live checks for ${retrySec}s.`);
          if (requestId === liveCheckRequestId && getPromptText(promptElement).trim() === text) {
            updateRiskIndicator('rate_limited', promptElement);
          }
          return;
        }

        if (!response.ok) {
          const error = response.error || `Backend returned HTTP ${response.status}`;
          throw new Error(error);
        }

        const data = response.data;
        if (requestId !== liveCheckRequestId || getPromptText(promptElement).trim() !== text) return;
        if (!['allow', 'redact', 'block'].includes(data.action)) {
          throw new Error(`Unexpected backend action: ${data.action}`);
        }
        updateRiskIndicator(data.action, promptElement, data.reason_detail);
        updateTextareaHighlights(promptElement, data.matches || [], data.action);
      } catch (err) {
        console.error('[Redactor] Error in live risk check:', err);
        if (requestId === liveCheckRequestId && getPromptText(promptElement).trim() === text) {
          updateRiskIndicator('unavailable', promptElement);
          updateTextareaHighlights(promptElement, [], null);
        }
      }
    }, delay);
  }

  // Listener for typing input in prompt element
  document.addEventListener('input', function (e) {
    const promptElement = findPromptElement();
    if (promptElement && (e.target === promptElement || promptElement.contains(e.target))) {
      onPromptInput(e, e.inputType === 'insertFromPaste' ? 100 : 600);
    }
  }, true);

  document.addEventListener('paste', function (e) {
    const promptElement = findPromptElement();
    if (!promptElement || (e.target !== promptElement && !promptElement.contains(e.target))) return;
    setTimeout(() => onPromptInput(e, 100), 0);
  }, true);

  // Listener for keydown (Enter) on prompt textarea
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      const promptElement = findPromptElement();
      if (promptElement && (e.target === promptElement || promptElement.contains(e.target))) {
        handleIntercept(e, promptElement);
      }
    }
  }, true);

  // Listener for click on send button
  document.addEventListener('click', function (e) {
    const sendButton = findSendButton();
    if (sendButton && (e.target === sendButton || sendButton.contains(e.target))) {
      const promptElement = findPromptElement();
      if (promptElement) {
        handleIntercept(e, promptElement);
      }
    }
  }, true);

  document.addEventListener('submit', function (e) {
    const form = e.target;
    const promptElement = findPromptElement();
    if (form instanceof HTMLFormElement && promptElement && form.contains(promptElement)) {
      handleIntercept(e, promptElement);
    }
  }, true);

  console.log('[Redactor] Extension initialized on ChatGPT.');
})();
