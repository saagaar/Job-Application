(() => {
  'use strict';

  const JT_ATTR = 'data-jt-injected';

  // ─── Debounce ────────────────────────────────────────────────────────────────
  function debounce(fn, ms) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  }

  // ─── Extract job from the right-hand detail panel ────────────────────────────
  function extractDetailJob() {
    const selTitle = [
      'h1.job-details-jobs-unified-top-card__job-title',
      '.job-details-jobs-unified-top-card__job-title a',
      '.jobs-unified-top-card__job-title h1',
      '.t-24.t-bold',
    ];
    const selCompany = [
      '.job-details-jobs-unified-top-card__company-name a',
      '.job-details-jobs-unified-top-card__company-name',
      '.jobs-unified-top-card__company-name a',
    ];
    const selLocation = [
      '.job-details-jobs-unified-top-card__bullet',
      '.jobs-unified-top-card__bullet',
    ];
    const selDesc = [
      '.jobs-description-content__text',
      '.jobs-box__html-content',
      '.jobs-description__content',
    ];

    const title    = firstText(selTitle);
    const company  = firstText(selCompany);
    const location = firstText(selLocation);
    const description = firstText(selDesc, true);

    if (!title || !company) return null;

    // Job URL: either current page (view) or ?currentJobId= param
    const params = new URLSearchParams(window.location.search);
    const jobId  = params.get('currentJobId');
    const url    = jobId
      ? `https://www.linkedin.com/jobs/view/${jobId}/`
      : window.location.href.split('?')[0];

    return { title, company, location, description, url, source: 'linkedin_extension' };
  }

  // ─── Extract job from a list card ────────────────────────────────────────────
  function extractCardJob(card) {
    const selTitle = [
      '.job-card-list__title--link',
      '.job-card-container__link',
      'a[data-control-name="job_card_title"]',
      '.artdeco-entity-lockup__title a',
    ];
    const selCompany = [
      '.artdeco-entity-lockup__subtitle span',
      '.job-card-container__primary-description',
      '.job-card-list__company-name',
    ];
    const selLocation = [
      '.job-card-container__metadata-item',
      '.artdeco-entity-lockup__caption span',
    ];

    const titleEl   = firstEl(selTitle, card);
    const companyEl = firstEl(selCompany, card);
    if (!titleEl || !companyEl) return null;

    const href = titleEl.href || titleEl.closest('a')?.href || '';
    const url  = href ? href.split('?')[0] : '';

    return {
      title:       titleEl.textContent.trim(),
      company:     companyEl.textContent.trim(),
      location:    firstText(selLocation, false, card),
      description: '',
      url,
      source: 'linkedin_extension',
    };
  }

  // ─── DOM helpers ─────────────────────────────────────────────────────────────
  function firstEl(selectors, root = document) {
    for (const s of selectors) {
      const el = root.querySelector(s);
      if (el) return el;
    }
    return null;
  }

  function firstText(selectors, multiline = false, root = document) {
    for (const s of selectors) {
      const el = root.querySelector(s);
      if (el) {
        return multiline
          ? el.innerText.trim()
          : el.textContent.trim();
      }
    }
    return '';
  }

  // ─── Storage helpers ─────────────────────────────────────────────────────────
  async function getSaved() {
    return new Promise(resolve => {
      chrome.storage.local.get('savedJobs', d => resolve(d.savedJobs || []));
    });
  }

  async function saveJob(job) {
    const saved = await getSaved();
    if (saved.some(j => j.url === job.url)) return false; // already saved
    saved.push({ ...job, savedAt: Date.now() });
    await chrome.storage.local.set({ savedJobs: saved });
    return true;
  }

  async function getCount() {
    const saved = await getSaved();
    return saved.length;
  }

  // ─── Floating Action Button (FAB) ────────────────────────────────────────────
  let fab;

  function createFab() {
    if (document.getElementById('jt-fab')) return;

    fab = document.createElement('div');
    fab.id = 'jt-fab';
    fab.innerHTML = `
      <div id="jt-fab-icon">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
        </svg>
      </div>
      <span id="jt-fab-badge" style="display:none">0</span>
      <span id="jt-fab-label">Save job</span>
    `;

    fab.addEventListener('click', async () => {
      const job = extractDetailJob();
      if (!job || !job.title) {
        showFabToast('No job selected — click a job listing first', 'warn');
        return;
      }
      const added = await saveJob(job);
      if (added) {
        showFabToast(`Saved: ${job.title}`, 'ok');
        updateFabBadge();
      } else {
        showFabToast('Already in your queue', 'info');
      }
    });

    document.body.appendChild(fab);
    updateFabBadge();
  }

  async function updateFabBadge() {
    if (!fab) return;
    const count = await getCount();
    const badge = document.getElementById('jt-fab-badge');
    if (!badge) return;
    if (count > 0) {
      badge.textContent = count;
      badge.style.display = 'flex';
    } else {
      badge.style.display = 'none';
    }
  }

  let toastTimer;
  function showFabToast(msg, type = 'ok') {
    let toast = document.getElementById('jt-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'jt-toast';
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.className = `jt-toast-${type} jt-toast-show`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('jt-toast-show'), 2500);
  }

  // ─── Card-level save buttons ──────────────────────────────────────────────────
  function injectCardButtons() {
    const cards = document.querySelectorAll(
      'li.scaffold-layout__list-item, li.jobs-search-results__list-item'
    );

    cards.forEach(card => {
      if (card.getAttribute(JT_ATTR)) return;
      card.setAttribute(JT_ATTR, '1');

      const job = extractCardJob(card);
      if (!job) return;

      const btn = document.createElement('button');
      btn.className = 'jt-card-btn';
      btn.title = 'Save to Job Tracker';
      btn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
        </svg>
      `;

      btn.addEventListener('click', async e => {
        e.stopPropagation();
        e.preventDefault();
        const added = await saveJob(job);
        if (added) {
          btn.classList.add('jt-card-btn--saved');
          btn.title = 'Saved!';
          showFabToast(`Saved: ${job.title}`, 'ok');
          updateFabBadge();
        } else {
          showFabToast('Already in your queue', 'info');
        }
      });

      // Mark already-saved cards
      getSaved().then(saved => {
        if (saved.some(j => j.url === job.url)) {
          btn.classList.add('jt-card-btn--saved');
          btn.title = 'Already saved';
        }
      });

      card.style.position = 'relative';
      card.appendChild(btn);
    });
  }

  // ─── Main init / re-run on navigation ────────────────────────────────────────
  function run() {
    createFab();
    injectCardButtons();
  }

  const debouncedRun = debounce(run, 600);

  // MutationObserver catches SPA DOM updates
  const mo = new MutationObserver(debouncedRun);
  mo.observe(document.body, { childList: true, subtree: true });

  // Catch pushState / replaceState SPA navigation
  const _pushState = history.pushState.bind(history);
  history.pushState = (...args) => { _pushState(...args); debouncedRun(); };
  window.addEventListener('popstate', debouncedRun);

  run();
})();
