// Central config for the extension. Change apiBase here to point at a different server,
// or update it at runtime via the popup settings panel (saved to chrome.storage.local).
const EXT_DEFAULTS = {
  apiBase: 'http://localhost:8000',
};

async function getApiBase() {
  return new Promise(resolve =>
    chrome.storage.local.get('apiBase', d => resolve(d.apiBase || EXT_DEFAULTS.apiBase))
  );
}

async function setApiBase(url) {
  return new Promise(resolve => chrome.storage.local.set({ apiBase: url.replace(/\/$/, '') }, resolve));
}
