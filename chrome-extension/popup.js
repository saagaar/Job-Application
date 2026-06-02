const $ = id => document.getElementById(id);

async function getSaved() {
  return new Promise(resolve => {
    chrome.storage.local.get('savedJobs', d => resolve(d.savedJobs || []));
  });
}

async function setSaved(jobs) {
  return new Promise(resolve => chrome.storage.local.set({ savedJobs: jobs }, resolve));
}

function setStatus(msg, type) {
  const bar = $('status-bar');
  bar.textContent = msg;
  bar.className = type;
}

function clearStatus() {
  $('status-bar').className = '';
  $('status-bar').textContent = '';
}

function renderList(jobs) {
  const list   = $('job-list');
  const empty  = $('empty-state');
  const footer = $('footer');

  list.innerHTML = '';

  if (!jobs.length) {
    empty.style.display  = 'block';
    footer.style.display = 'none';
    return;
  }

  empty.style.display  = 'none';
  footer.style.display = 'flex';

  jobs.forEach((job, idx) => {
    const item = document.createElement('div');
    item.className = 'job-item';
    item.innerHTML = `
      <div class="job-info">
        <div class="job-title" title="${esc(job.title)}">${esc(job.title)}</div>
        <div class="job-meta">${esc(job.company)}${job.location ? ' · ' + esc(job.location) : ''}</div>
      </div>
      <button class="remove-btn" data-idx="${idx}" title="Remove">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    `;
    list.appendChild(item);
  });

  list.querySelectorAll('.remove-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const idx  = parseInt(btn.dataset.idx, 10);
      const jobs = await getSaved();
      jobs.splice(idx, 1);
      await setSaved(jobs);
      clearStatus();
      renderList(jobs);
    });
  });
}

function esc(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Check API health
async function checkApi() {
  const dot = $('api-dot');
  const base = await getApiBase();
  try {
    await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: 'CHECK_API' }, res => {
        if (chrome.runtime.lastError || !res) reject();
        else res.ok ? resolve() : reject();
      });
    });
    dot.className = 'api-dot online';
    dot.title = `API online — ${base}`;
  } catch {
    dot.className = 'api-dot offline';
    dot.title = `API offline — start your local server (${base})`;
  }
}

// Send to backend
$('send-btn').addEventListener('click', async () => {
  const jobs  = await getSaved();
  const score = $('score-toggle').checked;
  if (!jobs.length) return;

  $('send-btn').disabled = true;
  $('send-btn').textContent = 'Sending…';
  const base = await getApiBase();
  setStatus(`Connecting to ${base}…`, 'info');

  chrome.runtime.sendMessage({ type: 'IMPORT_JOBS', jobs, score }, async res => {
    $('send-btn').disabled = false;
    $('send-btn').textContent = 'Send to Job Tracker';

    if (chrome.runtime.lastError || !res) {
      setStatus('Could not reach the API. Is the server running?', 'err');
      return;
    }
    if (!res.ok) {
      setStatus(`Error: ${res.error}`, 'err');
      return;
    }

    const { imported, skipped, scored } = res;
    let msg = `✓ ${imported} job${imported !== 1 ? 's' : ''} imported`;
    if (skipped)  msg += `, ${skipped} duplicate${skipped !== 1 ? 's' : ''} skipped`;
    if (scored)   msg += `, ${scored} scored`;
    setStatus(msg, 'ok');

    await setSaved([]);
    renderList([]);
  });
});

// Clear queue
$('clear-btn').addEventListener('click', async () => {
  await setSaved([]);
  clearStatus();
  renderList([]);
});

// Settings panel
async function initSettings() {
  const input = $('api-base-input');
  const saveBtn = $('api-base-save');
  if (!input || !saveBtn) return;

  input.value = await getApiBase();

  saveBtn.addEventListener('click', async () => {
    const url = input.value.trim();
    if (!url) return;
    await setApiBase(url);
    saveBtn.textContent = 'Saved!';
    setTimeout(() => { saveBtn.textContent = 'Save'; }, 1500);
    checkApi();
  });
}

// Boot
(async () => {
  const [jobs] = await Promise.all([getSaved(), checkApi(), initSettings()]);
  renderList(jobs);
})();
