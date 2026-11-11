// SPDX-License-Identifier: MPL-2.0

import { escapeHTML, href, loadData, snapshotFor } from './model.js';
import { api, methods, overview, performance, shell, testDetail, tests } from './views.js';
import * as realViews from './real-views.js';
import { executionRecord } from './ci-model.js';

const app = document.querySelector('#app');
const views = { overview, tests, api, performance, methods };
let data;
let state;
let dialogOpener;
let toastTimer;

function readState() {
  const result = Object.fromEntries(new URLSearchParams(location.search));
  result.view = Object.hasOwn(views, result.view) ? result.view : 'overview';
  result.arch = data.presentation.platforms.some(platform => platform.id === result.arch) ? result.arch : 'all';
  result.snapshot ||= 'latest';
  if (data.mode === 'real') {
    if (result.suite?.startsWith('nixos/')) {
      result.subsuite = result.suite;
      result.suite = 'nixos';
    }
    if (result.suite !== 'nixos') delete result.subsuite;
  }
  return result;
}

function render({ preserveScroll = false, preserveFocus = false } = {}) {
  const active = preserveFocus ? document.activeElement : null;
  const filter = active?.dataset.filter;
  const selection = active?.selectionStart;
  const scrollY = window.scrollY;
  state = readState();
  const snapshot = snapshotFor(data, state);
  const renderView = data.mode === 'real' ? realViews[state.view] : views[state.view];
  app.innerHTML = shell(data, state, snapshot, renderView(data, state, snapshot));
  document.title = `Asterinas QA · ${{ overview: 'Overview', tests: 'Test coverage', api: 'API coverage', performance: 'Performance', methods: 'Methods & data' }[state.view]}`;
  if (state.detail && state.view === 'tests') {
    const dialog = document.querySelector('#detail-dialog');
    dialog.innerHTML = (data.mode === 'real' ? realViews.testDetail : testDetail)(data, state, snapshot);
    dialog.showModal();
    dialog.addEventListener('cancel', event => { event.preventDefault(); closeDialog(); });
    dialog.addEventListener('click', event => { if (event.target === dialog) closeDialog(); });
  } else if (preserveFocus && filter) {
    const input = document.querySelector(`[data-filter="${filter}"]`);
    input?.focus({ preventScroll: true });
    if (selection != null && input?.type === 'search') input.setSelectionRange(selection, selection);
  }
  if (preserveScroll) window.scrollTo(0, scrollY);
  else window.scrollTo(0, 0);
}

function navigate(url, options = {}) {
  const previous = state.view;
  history[options.replace ? 'replaceState' : 'pushState']({}, '', url);
  render({ preserveScroll: options.preserveScroll ?? previous === readState().view, preserveFocus: options.preserveFocus });
}

function closeDialog() {
  const key = state.detail;
  navigate(href(state, { detail: null }), { replace: true, preserveScroll: true });
  const links = [...document.querySelectorAll('a[data-route]')];
  const opener = links.find(element => new URL(element.href).searchParams.get('detail') === key && element.getClientRects().length > 0);
  (opener ?? dialogOpener)?.focus({ preventScroll: true });
}

function download(content, name, type = 'application/json') {
  const objectURL = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement('a');
  anchor.href = objectURL;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(objectURL), 1000);
  const toast = document.querySelector('#toast');
  toast.textContent = `Downloaded ${name}`;
  toast.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('visible'), 2800);
}

document.addEventListener('click', event => {
  const apiDetails = event.target.closest('details[data-api] > summary')?.parentElement;
  if (apiDetails) {
    state.api = apiDetails.open ? null : apiDetails.dataset.api;
    history.replaceState({}, '', href(state));
  }
  const route = event.target.closest('a[data-route]');
  if (route && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
    event.preventDefault();
    dialogOpener = route;
    navigate(route.href);
    return;
  }
  if (event.target.closest('[data-close-dialog]')) closeDialog();
  const report = event.target.closest('[data-download-report]');
  if (report) download(JSON.stringify(data.byID.get(report.dataset.downloadReport), null, 2), 'qa-example-report.json');
  const observation = event.target.closest('[data-download-job]');
  if (observation) {
    const job = executionRecord(data, observation.dataset.downloadJob);
    download(JSON.stringify(job, null, 2), `qa-job-${job.origin_job_id}.json`);
  }
  const button = event.target.closest('[data-download]');
  if (button?.dataset.download === 'data') {
    const { byID, ...serializable } = data;
    download(JSON.stringify(serializable, null, 2), data.mode === 'real' ? 'qa-source-observations.json' : 'qa-demo-records.json');
  }
  if (button?.dataset.download === 'chart') {
    const chart = document.querySelector('#trend-chart').cloneNode(true);
    chart.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    download(new XMLSerializer().serializeToString(chart), data.mode === 'real' ? 'qa-published-measurements.svg' : 'qa-example-trend.svg', 'image/svg+xml');
  }
  const point = event.target.closest('[data-point]');
  if (point) {
    navigate(href(state, { point: point.dataset.point }), { replace: true, preserveScroll: true });
    document.querySelector(`[data-point="${point.dataset.point}"]`)?.focus({ preventScroll: true });
  }
});

document.addEventListener('keydown', event => {
  if (event.target.matches('[data-point]') && ['Enter', ' '].includes(event.key)) {
    event.preventDefault();
    event.target.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  }
});

document.addEventListener('change', event => {
  const key = event.target.dataset.filter;
  if (key && event.target.type !== 'search') navigate(href(state, { [key]: event.target.value, ...(key === 'suite' ? { subsuite: null } : {}), detail: null, point: null }), { preserveFocus: true });
});

document.addEventListener('input', event => {
  if (!event.isComposing && event.target.type === 'search' && event.target.dataset.filter) {
    navigate(href(state, { [event.target.dataset.filter]: event.target.value, api: null }), { replace: true, preserveScroll: true, preserveFocus: true });
  }
});

document.addEventListener('compositionend', event => {
  if (event.target.type === 'search' && event.target.dataset.filter) {
    navigate(href(state, { [event.target.dataset.filter]: event.target.value, api: null }), { replace: true, preserveScroll: true, preserveFocus: true });
  }
});

document.addEventListener('toggle', event => {
  if (event.target.matches('details[data-api]')) {
    if (event.target.open) state.api = event.target.dataset.api;
    else if (state.api === event.target.dataset.api) state.api = null;
    history.replaceState({}, '', href(state));
  }
}, true);

window.addEventListener('popstate', () => render({ preserveScroll: true }));

try {
  data = await loadData();
  render();
  // Re-evaluate age without claiming that the static site collected new data.
  setInterval(() => { if (!state.detail && !document.querySelector('input:focus')) render({ preserveScroll: true }); }, 300000);
} catch (error) {
  app.innerHTML = `<main class="loading error-screen"><h1>Unable to load the snapshot</h1><p>${escapeHTML(error.message)}</p><p>Open this page through a static HTTP server and check the JSON file in <code>data/</code>.</p><button onclick="location.reload()">Reload</button></main>`;
}
