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
    return (
      document.querySelector('#prompt-textarea') ||
      document.querySelector('textarea') ||
      document.querySelector('div[contenteditable="true"]')
    );
  }

  // Find ChatGPT send button
  function findSendButton() {
    return (
      document.querySelector('button[data-testid="send-button"]') ||
      document.querySelector('button[aria-label*="Send"]') ||
      document.querySelector('form button[type="submit"]')
    );
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

  // Core handler for checking prompt
  async function handleIntercept(e, promptElement) {
    if (isBypassingCheck) return;

    const text = getPromptText(promptElement).trim();
    if (!text) return;

    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    try {
      const response = await fetch('http://localhost:8000/check', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text })
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();

      if (data.action === 'allow') {
        updateRiskIndicator(null, promptElement);
        updateTextareaHighlights(promptElement, [], null);
        triggerSubmit(promptElement);
      } else if (data.action === 'redact') {
        if (data.redacted_text) {
          setPromptText(promptElement, data.redacted_text);
        }
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
        // Default allow if unknown action
        updateRiskIndicator(null, promptElement);
        updateTextareaHighlights(promptElement, [], null);
        triggerSubmit(promptElement);
      }
    } catch (err) {
      console.error('[Redactor] Error checking prompt:', err);
      // Fail-open or prompt user if server is offline
      createToast('Redactor backend offline. Sending normally.', 3000, true);
      triggerSubmit(promptElement);
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

  // Live inline overlay preview for matched redaction spans
  function updateTextareaHighlights(promptElement, matches, action) {
    let backdrop = document.getElementById('redactor-textarea-backdrop');

    if (!promptElement || !matches || matches.length === 0) {
      if (backdrop) backdrop.style.display = 'none';
      return;
    }

    const text = getPromptText(promptElement);
    if (!text) {
      if (backdrop) backdrop.style.display = 'none';
      return;
    }

    const parent = promptElement.closest('form') || promptElement.parentElement;
    if (!parent) return;

    const computedParent = window.getComputedStyle(parent);
    if (computedParent.position === 'static') {
      parent.style.position = 'relative';
    }

    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.id = 'redactor-textarea-backdrop';
      parent.appendChild(backdrop);
    }

    const rect = promptElement.getBoundingClientRect();
    const parentRect = parent.getBoundingClientRect();
    const style = window.getComputedStyle(promptElement);

    backdrop.style.cssText = `
      position: absolute;
      top: ${rect.top - parentRect.top}px;
      left: ${rect.left - parentRect.left}px;
      width: ${rect.width}px;
      height: ${rect.height}px;
      padding: ${style.padding};
      margin: ${style.margin};
      box-sizing: ${style.boxSizing};
      font-family: ${style.fontFamily};
      font-size: ${style.fontSize};
      font-weight: ${style.fontWeight};
      line-height: ${style.lineHeight};
      letter-spacing: ${style.letterSpacing};
      white-space: pre-wrap;
      word-wrap: break-word;
      word-break: break-word;
      color: transparent;
      pointer-events: none;
      z-index: 4;
      overflow: hidden;
      display: block;
    `;

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
    }

    indicator.title = reasonDetail || labelText;
    indicator.innerHTML = `<span style="width:7px; height:7px; border-radius:50%; background-color:${dotColor}; display:inline-block;"></span><span>${labelText}</span>`;
  }

  // Debounced live risk check on typing
  let debounceTimer = null;

  function onPromptInput(e) {
    clearTimeout(debounceTimer);
    const promptElement = findPromptElement();
    if (!promptElement) return;

    const text = getPromptText(promptElement).trim();
    if (!text) {
      updateRiskIndicator(null, promptElement);
      updateTextareaHighlights(promptElement, [], null);
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const response = await fetch('http://localhost:8000/check', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text })
        });
        if (response.ok) {
          const data = await response.json();
          updateRiskIndicator(data.action, promptElement, data.reason_detail);
          updateTextareaHighlights(promptElement, data.matches || [], data.action);
        }
      } catch (err) {
        console.error('[Redactor] Error in live risk check:', err);
      }
    }, 600);
  }

  // Listener for typing input in prompt element
  document.addEventListener('input', function (e) {
    const promptElement = findPromptElement();
    if (promptElement && (e.target === promptElement || promptElement.contains(e.target))) {
      onPromptInput(e);
    }
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

  console.log('[Redactor] Extension initialized on ChatGPT.');
})();
