/**
 * Support Brain - Embeddable Customer Chat Widget
 * 
 * Usage on external website:
 * <script src="https://YOUR_BACKEND_OR_WIDGET_URL/widget.js"
 *         data-business-token="PUBLIC_WIDGET_TOKEN"></script>
 */
(function () {
  'use strict';

  // Read configuration from the script tag
  const scriptTag = document.currentScript || document.querySelector('script[data-business-token]');
  if (!scriptTag) {
    console.error('Support Brain Widget: missing script tag with data-business-token.');
    return;
  }

  const businessToken = scriptTag.getAttribute('data-business-token');
  let backendUrl = scriptTag.getAttribute('data-backend-url');
  if (!backendUrl && scriptTag.src) {
    try {
      backendUrl = new URL(scriptTag.src).origin;
    } catch (e) {
      backendUrl = 'http://localhost:8000';
    }
  }
  backendUrl = backendUrl || 'http://localhost:8000';

  if (!businessToken) {
    console.error('Support Brain Widget: data-business-token is required.');
    return;
  }

  // Create floating widget container
  const container = document.createElement('div');
  container.id = 'support-brain-widget-root';
  container.innerHTML = `
    <style>
      #support-brain-widget-root {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 999999;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }
      #support-brain-trigger {
        width: 56px;
        height: 56px;
        border-radius: 50%;
        background: #2563eb;
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
        cursor: pointer;
        border: none;
        transition: transform 0.2s;
      }
      #support-brain-trigger:hover {
        transform: scale(1.05);
      }
      #support-brain-iframe-container {
        display: none;
        position: fixed;
        bottom: 96px;
        right: 24px;
        width: 380px;
        height: 600px;
        max-width: calc(100vw - 32px);
        max-height: calc(100vh - 120px);
        box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        border-radius: 16px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
        background: #ffffff;
      }
      #support-brain-iframe-container.open {
        display: block;
      }
      #support-brain-iframe {
        width: 100%;
        height: 100%;
        border: none;
      }
    </style>
    <div id="support-brain-iframe-container">
      <iframe id="support-brain-iframe" src="${backendUrl}/api/widget/iframe?token=${encodeURIComponent(businessToken)}" title="Customer Support Chat"></iframe>
    </div>
    <button id="support-brain-trigger" aria-label="Open support chat">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
      </svg>
    </button>
  `;

  document.body.appendChild(container);

  const trigger = document.getElementById('support-brain-trigger');
  const iframeBox = document.getElementById('support-brain-iframe-container');

  trigger.addEventListener('click', () => {
    iframeBox.classList.toggle('open');
  });
})();
