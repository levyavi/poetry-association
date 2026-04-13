let currentAbortController = null;

function initModal() {
  const modal = document.querySelector('.modal');
  const resultsSection = document.querySelector('.results');
  const closeButton = document.querySelector('.modal__close-button');
  const copyButton = document.querySelector('.modal__copy-button');
  const overlay = document.querySelector('.modal__overlay');

  if (!resultsSection) return;

  // Delegated click handler on results section
  resultsSection.addEventListener('click', (event) => {
    const resultItem = event.target.closest('[data-poem-id]');
    if (resultItem) {
      const id = resultItem.getAttribute('data-poem-id');
      openModal(parseInt(id, 10));
    }
  });

  // Close button click
  if (closeButton) {
    closeButton.addEventListener('click', closeModal);
  }

  // Overlay (backdrop) click
  if (overlay) {
    overlay.addEventListener('click', closeModal);
  }

  // Copy button click
  if (copyButton) {
    copyButton.addEventListener('click', copyPoem);
  }

  // Escape key handler
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal && !modal.hidden) {
      closeModal();
    }
  });
}

function openModal(id) {
  const modal = document.querySelector('.modal');
  const titleEl = document.querySelector('[data-modal-title]');
  const bodyEl = document.querySelector('[data-modal-body]');

  if (!modal || !titleEl || !bodyEl) return;

  // Cancel any previous fetch
  if (currentAbortController) {
    currentAbortController.abort();
  }

  currentAbortController = new AbortController();

  // Show loading state briefly
  modal.hidden = false;
  titleEl.textContent = 'Loading...';
  bodyEl.textContent = '';

  fetch(`/poems/${id}`, { signal: currentAbortController.signal })
    .then((response) => {
      if (!response.ok) {
        throw new Error('Failed to load poem');
      }
      return response.json();
    })
    .then((data) => {
      const displayTitle = data.title && data.title.trim() ? data.title : 'Untitled';
      titleEl.textContent = displayTitle;
      bodyEl.textContent = data.text;
      // Reset copy button state
      const copyButton = document.querySelector('.modal__copy-button');
      if (copyButton) {
        copyButton.textContent = 'Copy';
      }
    })
    .catch((error) => {
      if (error.name !== 'AbortError') {
        titleEl.textContent = 'Error';
        bodyEl.textContent = 'Could not load poem.';
      }
    });
}

function closeModal() {
  const modal = document.querySelector('.modal');
  if (modal) {
    modal.hidden = true;
    const bodyEl = document.querySelector('[data-modal-body]');
    if (bodyEl) {
      bodyEl.textContent = '';
    }
  }
}

function copyPoem() {
  const titleEl = document.querySelector('[data-modal-title]');
  const bodyEl = document.querySelector('[data-modal-body]');
  const copyButton = document.querySelector('.modal__copy-button');
  if (!titleEl || !bodyEl || !copyButton) return;

  const title = titleEl.textContent.trim();
  const body = bodyEl.textContent;
  const text = body ? `${title}\n\n${body}` : title;

  // Try async clipboard API first
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        showCopySuccess();
      })
      .catch(() => {
        fallbackCopy(text);
      });
  } else {
    fallbackCopy(text);
  }
}

function fallbackCopy(text) {
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);

  try {
    textarea.select();
    const success = document.execCommand('copy');
    if (success) {
      showCopySuccess();
    } else {
      showCopyFailure();
    }
  } catch {
    showCopyFailure();
  } finally {
    document.body.removeChild(textarea);
  }
}

function showCopySuccess() {
  const copyButton = document.querySelector('.modal__copy-button');
  if (!copyButton) return;

  const originalText = copyButton.textContent;
  copyButton.textContent = 'Copied';

  setTimeout(() => {
    copyButton.textContent = originalText;
  }, 1500);
}

function showCopyFailure() {
  const copyButton = document.querySelector('.modal__copy-button');
  if (!copyButton) return;

  const originalText = copyButton.textContent;
  copyButton.textContent = 'Copy failed';

  setTimeout(() => {
    copyButton.textContent = originalText;
  }, 1500);
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', initModal);
