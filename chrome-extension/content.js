(() => {
  'use strict';

  const JT_ATTR = 'data-jt-injected';

  // ─── Utilities ───────────────────────────────────────────────────────────────
  function debounce(fn, ms) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  }

  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

  // Extract a query-param value straight from a URL string.
  // Using href + regex instead of window.location.search because LinkedIn's
  // SPA pushState can leave .search stale/empty after navigation.
  function getParam(param, url = window.location.href) {
    const match = url.match(new RegExp('[?&]' + param + '=([^&#+]*)'));
    return match ? decodeURIComponent(match[1]) : null;
  }

  // ─── Extract job from the right-hand detail panel ────────────────────────────
  //
  // Class-free approach: LinkedIn's CSS classes are dynamic and change on every
  // deploy. Instead we rely on structural HTML that never changes:
  //   - <h1> is always the job title on a job detail page
  //   - document.title follows "Job Title at Company | LinkedIn"
  //   - document.body.innerText captures everything for LLM processing
  //
  // Click LinkedIn's "…see more" button so the full job description is in the
  // DOM before we scrape it — otherwise the text is truncated/clamped.
  // Only matches a <span> with "more" text that sits inside a <button>,
  // which itself sits inside a <p> — the structure of LinkedIn's
  // description expander.
  function clickSeeMore() {
    const candidates = document.querySelectorAll('p button span');
    for (const el of candidates) {
      const text = el.textContent?.trim().toLowerCase().replace(/[…\.]+$/, '');
      if (/^(see|show)?\s*more$/.test(text)) {
        el.closest('button').click();
        return true;
      }
    }
    return false;
  }

  // Find the "About the job" button/heading and read the <p> tag(s) that sit
  // next to it — this is the actual job description, without the feed
  // sidebar / company "About" section / footer that body-wide scraping picks up.
  function extractAboutJobDescription() {
    const heading = Array.from(document.querySelectorAll('button, h2, h3'))
      .find(el => el.textContent?.trim().toLowerCase() === 'about the job');
    if (!heading) return '';

    // Walk up until we find an ancestor (or the heading itself) that has a
    // next sibling element — that sibling holds the description content.
    let node = heading;
    let container = node.nextElementSibling;
    while (!container && node.parentElement) {
      node = node.parentElement;
      container = node.nextElementSibling;
    }
    if (!container) return '';

    const paragraphs = container.matches('p')
      ? [container]
      : Array.from(container.querySelectorAll('p'));

    return paragraphs.map(p => p.innerText.trim()).filter(Boolean).join('\n\n');
  }

  // expandDescription: only true on an explicit user action (Save job click) —
  // we don't want to click LinkedIn's UI automatically on page load/navigation.
  async function extractDetailJob(expandDescription = false) {
    // Expand the description first, then give the DOM a moment to re-render
    // before reading it back out.
    if (expandDescription && clickSeeMore()) await wait(300);

    // Title: read from og:title meta tag ("Job Title at Company"), strip the company suffix.
    // Falls back to document.title which follows the same pattern.
    const ogTitle = document.querySelector('meta[property="og:title"]')?.content ||
                    document.querySelector('meta[name="title"]')?.content || '';
    const title = ogTitle
      ? ogTitle.replace(/\s+at\s+.+$/, '').trim()
      : document.title.replace(/\s+at\s+.+$/, '').replace(/\s*[|–\-].*$/, '').trim();

    // Company: parse document.title ("Job Title at Company | LinkedIn"),
    // fall back to the first /company/ anchor visible on the page.
    let company = '';
    const titleMatch = document.title.match(/^.+?\s+at\s+(.+?)\s*[|–\-]/);
    if (titleMatch) {
      company = titleMatch[1].trim();
    } else {
      company = document.querySelector('a[href*="/company/"]')?.innerText?.trim() || '';
    }

    if (!title || !company) return null;

    // Cross-validate job IDs: if the URL's currentJobId and the panel's
    // data-occludable-job-id disagree, the panel is still rendering — return
    // null so the FAB retry loop tries again after a short wait.
    const urlJobId = getParam('currentJobId') ||
                     window.location.pathname.match(/\/jobs\/view\/(\d+)/)?.[1];
    const domJobId = document.querySelector('[data-occludable-job-id]')
                       ?.getAttribute('data-occludable-job-id') ||
                     document.querySelector('[data-job-id]')
                       ?.getAttribute('data-job-id');
    if (urlJobId && domJobId && urlJobId !== domJobId) return null;

    const jobId = urlJobId || domJobId;
    const url   = jobId
      ? `https://www.linkedin.com/jobs/view/${jobId}/`
      : window.location.href.split(/[?#]/)[0];

    // Prefer the targeted "About the job" paragraphs; fall back to a
    // body-wide leaf-level <p>/<li> scrape if that section isn't found.
    // Filtering to nodes that contain no nested p/li ensures we get the deepest
    // text at every branch without double-counting parent containers.
    const description = extractAboutJobDescription() ||
      Array.from(document.querySelectorAll('p, li'))
        .filter(el => !el.querySelector('p, li'))
        .map(el => el.innerText.trim())
        .filter(t => t.length > 0)
        .join('\n');
    const keywords = getParam('keywords') || '';
    const geoId    = getParam('geoId')    || '';

    return {
      title, company, description, url,
      source: 'linkedin_extension',
      ...(keywords && { keywords }),
      ...(geoId    && { geoId }),
    };
  }

  // ─── Extract job from a list card ────────────────────────────────────────────
  //
  // Cards use aria-label (format: "Job Title at Company") as the primary source
  // since it is a semantic attribute LinkedIn sets for accessibility and is
  // independent of CSS class names. Falls back to the first /jobs/view/ link.
  //
  function extractCardJob(card) {
    let title = '', company = '';

    // aria-label on the card element is the most stable signal
    const ariaLabel = card.getAttribute('aria-label') || '';
    const ariaMatch = ariaLabel.match(/^(.+?)\s+at\s+(.+?)$/);
    if (ariaMatch) {
      title   = ariaMatch[1].trim();
      company = ariaMatch[2].trim();
    } else {
      // Fallback: first job-view link text is the title
      title = card.querySelector('a[href*="/jobs/view/"]')?.innerText?.trim() ||
              card.querySelector('a')?.innerText?.trim() || '';
    }

    if (!title) return null;

    // Job URL: prefer data attribute (stable), then link href
    const attrJobId = card.getAttribute('data-occludable-job-id') ||
                      card.getAttribute('data-job-id') ||
                      card.closest('[data-occludable-job-id]')?.getAttribute('data-occludable-job-id');
    const linkHref  = card.querySelector('a[href*="/jobs/view/"]')?.href || '';
    const viewMatch = linkHref.match(/\/jobs\/view\/(\d+)/);
    const qJobId    = getParam('currentJobId', linkHref);
    const jobId     = (viewMatch && viewMatch[1]) || qJobId || attrJobId;
    if (!jobId) return null;

    return {
      title,
      company,
      location:    '',
      description: '',
      url:         `https://www.linkedin.com/jobs/view/${jobId}/`,
      source:      'linkedin_extension',
    };
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
      // Try immediately, then retry twice (detail panel may still be rendering)
      let job = await extractDetailJob(true);
      if (!job) {
        showFabToast('Reading job…', 'info');
        await wait(600);
        job = await extractDetailJob(true);
      }
      if (!job) {
        await wait(800);
        job = await extractDetailJob(true);
      }
      if (!job || !job.title) {
        showFabToast('Could not read job — try clicking the listing first', 'warn');
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
    // Cast a wide net across every LinkedIn jobs page variant:
    //   /jobs/search/         → scaffold-layout__list-item
    //   /jobs/search-results/ → jobs-search-results__list-item or data-occludable-job-id
    //   /jobs/collections/    → same scaffold pattern
    //   /jobs/view/           → no list, FAB handles it
    const cards = document.querySelectorAll([
      'li.scaffold-layout__list-item',
      'li.jobs-search-results__list-item',
      'li[class*="scaffold-layout__list-item"]',
      'li[class*="search-results__list-item"]',
      'li[class*="job-card"]',
      'li[data-occludable-job-id]',
      'div[data-occludable-job-id]',
    ].join(', '));

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

  // ─── Job-detected banner ─────────────────────────────────────────────────────
  let lastBannerUrl = '';
  let bannerTimer;

  function showJobBanner(job) {
    if (job.url === lastBannerUrl) return;   // already shown for this listing
    lastBannerUrl = job.url;

    let banner = document.getElementById('jt-banner');
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'jt-banner';
      banner.innerHTML = `
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <rect x="2" y="7" width="20" height="14" rx="2"/>
          <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
        </svg>
        <span id="jt-banner-text"></span>
        <button id="jt-banner-close" title="Dismiss">&#x2715;</button>
      `;
      document.body.appendChild(banner);
      document.getElementById('jt-banner-close')
        .addEventListener('click', hideBanner);
    }

    const title = job.title.length > 38 ? job.title.slice(0, 36) + '…' : job.title;
    document.getElementById('jt-banner-text').textContent =
      `Job Tracker · ${title} at ${job.company}`;

    clearTimeout(bannerTimer);
    banner.classList.add('jt-banner-show');
    bannerTimer = setTimeout(hideBanner, 3000);
  }

  function hideBanner() {
    const banner = document.getElementById('jt-banner');
    if (banner) banner.classList.remove('jt-banner-show');
  }

  // ─── Jobs-page detection ─────────────────────────────────────────────────────
  // Covers every known LinkedIn jobs URL:
  //   /jobs/search/           standard search
  //   /jobs/search-results/   search-results view (with ?currentJobId=)
  //   /jobs/view/{id}/        direct job detail
  //   /jobs/collections/      curated collections
  //   /jobs/recommended/      recommended jobs
  //   /my-items/saved-jobs/   LinkedIn's own saved jobs list
  //   any URL with ?currentJobId= (e.g. showHowYouFit flow)
  function isJobsPage() {
    const path = window.location.pathname;

    return (
      path.startsWith('/jobs/') ||
      path === '/jobs'          ||
      path.startsWith('/my-items/saved-jobs') ||
      getParam('currentJobId') !== null        // reads from href, not stale .search
    );
  }

  // ─── Main init / re-run on navigation ────────────────────────────────────────
  async function run() {
    if (!isJobsPage()) {
      // If we navigated away from jobs, hide the FAB but keep the script alive
      const existingFab = document.getElementById('jt-fab');
      if (existingFab) existingFab.style.display = 'none';
      hideBanner();
      return;
    }

    // Back on a jobs page — restore FAB if it was hidden
    const existingFab = document.getElementById('jt-fab');
    if (existingFab) existingFab.style.display = '';

    createFab();
    injectCardButtons();
    const job = await extractDetailJob();
    if (job) showJobBanner(job);
  }

  const debouncedRun = debounce(run, 600);

  // MutationObserver catches SPA DOM updates (LinkedIn re-renders on navigation)
  const mo = new MutationObserver(debouncedRun);
  mo.observe(document.body, { childList: true, subtree: true });

  // Intercept SPA navigation so run() fires on every URL change,
  // even when LinkedIn moves from /feed/ → /jobs/ without a full reload
  const _pushState = history.pushState.bind(history);
  history.pushState = (...args) => { _pushState(...args); debouncedRun(); };
  window.addEventListener('popstate', debouncedRun);

  run();
})();
