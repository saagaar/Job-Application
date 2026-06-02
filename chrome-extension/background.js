importScripts('config.js');

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'IMPORT_JOBS') {
    importJobs(msg.jobs, msg.score)
      .then(result => sendResponse({ ok: true, ...result }))
      .catch(err  => sendResponse({ ok: false, error: err.message }));
    return true; // keep channel open for async response
  }

  if (msg.type === 'CHECK_API') {
    getApiBase().then(base =>
      fetch(`${base}/health`)
        .then(r => sendResponse({ ok: r.ok }))
        .catch(() => sendResponse({ ok: false }))
    );
    return true;
  }
});

async function importJobs(jobs, score = true) {
  const base = await getApiBase();
  const res = await fetch(`${base}/api/jobs/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jobs, score }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}
