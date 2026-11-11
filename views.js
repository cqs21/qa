// SPDX-License-Identifier: MPL-2.0

import { apiStatuses, countRows, escapeHTML as e, formatDate, formatNumber as n, formatTime, href, performanceRows, resultAge, rowsFor, shortSHA, statuses, summarize } from './model.js';

const paths = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.4"/><rect x="14" y="3" width="7" height="7" rx="1.4"/><rect x="3" y="14" width="7" height="7" rx="1.4"/><rect x="14" y="14" width="7" height="7" rx="1.4"/>',
  tests: '<path d="M9 3h6v4l5 11a2 2 0 0 1-2 3H6a2 2 0 0 1-2-3L9 7V3Z"/><path d="M7 14h10M8 3h8"/>',
  code: '<path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 18"/>',
  chart: '<path d="M3 3v18h18M6 15l4-5 4 3 7-8"/>',
  book: '<path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1v15"/>',
  arrow: '<path d="M4 12h15m-6-6 6 6-6 6"/>',
  external: '<path d="M14 3h7v7m0-7L10 14M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5"/>',
  branch: '<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M6 7v10m12-10a8 8 0 0 1-8 8H6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  cross: '<path d="m6 6 12 12M6 18 18 6"/>',
  alert: '<path d="M12 8v5m0 3h.01M10.3 3.5 2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.5a2 2 0 0 0-3.4 0Z"/>',
  activity: '<path d="M2 12h5l3-8 4 16 3-8h5"/>',
  slash: '<circle cx="12" cy="12" r="9"/><path d="m6 6 12 12"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Zm0 0v6h6M8 13h8m-8 4h5"/>',
  minus: '<path d="M6 12h12"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 1v5m6-5v5M9 18v5m6-5v5M1 9h5m-5 6h5m12-6h5m-5 6h5"/><rect x="10" y="10" width="4" height="4"/>',
  github: '<path d="M9 19c-4 1-4-2-6-2m12 5v-4a3.5 3.5 0 0 0-1-3c3 0 6-1 6-6a5 5 0 0 0-1-3 5 5 0 0 0 0-4s-2 0-4 2a14 14 0 0 0-6 0C7 2 5 2 5 2a5 5 0 0 0 0 4 5 5 0 0 0-1 3c0 5 3 6 6 6a3.5 3.5 0 0 0-1 3v4"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
  layers: '<path d="m12 3 10 5-10 5L2 8l10-5ZM2 12l10 5 10-5M2 16l10 5 10-5"/>',
};

export const icon = (name, className = '') => `<svg class="icon ${className}" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] ?? paths.file}</svg>`;
const nav = [['overview', 'grid', 'Overview', 'Project quality'], ['tests', 'tests', 'Test coverage', 'Suites & configurations'], ['api', 'code', 'API coverage', 'Syscalls & flags'], ['performance', 'chart', 'Performance', 'Linux comparisons'], ['methods', 'book', 'Methods & data', 'Sources & definitions']];

export function badge(status, label) {
  const detail = statuses[status] ?? statuses.unknown;
  return `<span class="badge ${detail.tone}">${icon(detail.symbol)}${e(label ?? detail.label)}</span>`;
}

export function apiBadge(status) {
  const detail = apiStatuses[status] ?? apiStatuses.not_assessed;
  return `<span class="badge ${detail.tone}"><span class="status-dot"></span>${detail.label}</span>`;
}

export function link(state, patch, text, className = 'text-link') {
  return `<a data-route href="${e(href(state, patch))}" class="${className}">${text}</a>`;
}

export function sectionHeader(eyebrow, title, action = '') {
  return `<div class="section-heading"><div><div class="eyebrow">${eyebrow}</div><h2>${title}</h2></div>${action}</div>`;
}

export function emptyState(title, description, state, patch) {
  return `<div class="empty-state">${icon('search')}<h3>${e(title)}</h3><p>${e(description)}</p>${patch ? link(state, patch, 'Clear filters ' + icon('arrow'), 'button secondary') : ''}</div>`;
}

export function shell(data, state, snapshot, content) {
  const currentNav = nav.find(item => item[0] === state.view) ?? nav[0];
  return `<aside class="sidebar" aria-label="Main navigation">
    <a class="brand" data-route href="${e(href(state, { view: 'overview', detail: null }))}" aria-label="Asterinas QA overview"><img src="./assets/asterinas.svg" width="156" height="41" alt="Asterinas"><span class="brand-qa">QA</span></a>
    <div class="sidebar-caption">PROJECT QUALITY</div>
    <nav>${nav.map(([view, glyph, label, description]) => `<a data-route href="${e(href(state, { view, detail: null, q: null, status: null, suite: null, subsuite: null, category: null, api: null }))}" class="nav-item ${state.view === view ? 'active' : ''}" ${state.view === view ? 'aria-current="page"' : ''}>${icon(glyph)}<span>${label}<small>${description}</small></span>${state.view === view ? '<span class="nav-active-dot"></span>' : ''}</a>`).join('')}</nav>
    <div class="sidebar-bottom"><div class="sidebar-note"><span class="sidebar-note-mark">✳</span><strong>Built on evidence.</strong><p>Scope, configuration, time, and sources<br>behind every result.</p></div><a href="https://asterinas.github.io/book/" target="_blank" rel="noopener noreferrer">Asterinas Book ${icon('external')}</a><a href="https://github.com/asterinas/asterinas" target="_blank" rel="noopener noreferrer">GitHub ${icon('external')}</a><div class="sidebar-version"><span class="status-dot"></span> QA DESIGN PREVIEW <span>v0.1</span></div></div>
  </aside>
  <div class="workspace"><header class="topbar"><div class="breadcrumb">Asterinas <span>/</span> Quality <span>/</span> <strong>${currentNav[2]}</strong></div><div class="topbar-right"><span class="public-label"><span class="status-dot"></span> Public preview</span><a href="https://github.com/asterinas/asterinas" aria-label="Visit Asterinas on GitHub" target="_blank" rel="noopener noreferrer">${icon('github')}</a></div></header>
    <div class="demo-banner ${data.mode === 'real' ? 'real-banner' : ''}">${icon('info')}<span>${data.mode === 'real' ? '<strong>Public source data</strong> Actions logs, versioned Book declarations, and published benchmark history. Each source retains its own date and scope.' : '<strong>Demo data</strong> Fictional records illustrate the design and interactions; they are not actual Asterinas results.'}</span>${link(state, { view: 'methods', detail: null }, 'About this data ' + icon('arrow'))}</div>
    <main id="main" class="main-content">${content}</main>
    <footer class="footer"><span><strong>ASTERINAS</strong> · A general-purpose OS in safe Rust.</span><span>Evidence before conclusions <span class="footer-dot">·</span> ${data.mode === 'real' ? 'Independent source dates · Methods & data' : shortSHA(snapshot.main_sha) + ' / Example snapshot'}</span></footer>
  </div><dialog id="detail-dialog" class="detail-dialog" aria-labelledby="detail-title"></dialog><div id="toast" class="toast" role="status"></div>`;
}

export function pageHeader(data, state, snapshot, eyebrow, title, description) {
  return `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div><label class="snapshot-select">${icon('layers')}<span class="sr-only">Select snapshot</span><select data-filter="snapshot" aria-label="Select snapshot">${data.snapshots.map((item, index) => `<option value="${index ? item.main_sha : 'latest'}" ${item.main_sha === snapshot.main_sha ? 'selected' : ''}>${index ? 'Historical snapshot' : 'Latest main'} · ${shortSHA(item.main_sha)}</option>`).join('')}</select></label></div>
  <div class="snapshot-bar"><span class="branch-label">${icon('branch')} ${snapshot === data.snapshots[0] ? 'main' : 'Historical snapshot'}</span><code>${shortSHA(snapshot.main_sha)}</code><span class="snapshot-divider"></span><span>${icon('clock')} Snapshot generated ${formatTime(snapshot.generated_at)}</span><span class="snapshot-bar-right">${snapshot === data.snapshots[0] ? '<span class="status-dot"></span>Current status and historical results shown separately' : 'Review the test scope recorded at the time'}</span></div>`;
}

export function platformTabs(data, state) {
  return `<div class="platform-tabs" aria-label="Filter architecture and environment">${[{ id: 'all', label: 'All architectures' }, ...data.presentation.platforms].map(platform => link(state, { arch: platform.id, detail: null, api: null }, `${platform.id === 'all' ? icon('layers') : ''}${e(platform.label)}${platform.id === 'tdx' ? '<span class="tab-mini">x86</span>' : ''}`, `platform-tab ${state.arch === platform.id ? 'selected' : ''}`)).join('')}</div>`;
}

function statCards(rows) {
  const counts = countRows(rows);
  return `<div class="stat-grid">${[
    ['Expected configs', counts.expected, `${counts.selected} selected · ${counts.received} reports`, 'layers', 'neutral'],
    ['Verified passes', counts.passed, 'Identity, configuration, and complete report verified', 'check', 'green'],
    ['Test failures', counts.failed, 'Assertions, stages, and evidence preserved', 'cross', 'red'],
    ['Unresolved', counts.unresolved, 'In progress, blocked, cancelled, or missing evidence', 'clock', 'amber'],
  ].map(([title, value, description, glyph, tone]) => `<article class="stat-card ${tone}"><div class="stat-label">${title}<span class="stat-icon">${icon(glyph)}</span></div><div class="stat-value">${value}<span>configs</span></div><p>${description}</p></article>`).join('')}</div>`;
}

function matrix(data, state, snapshot, compact = false) {
  const rows = rowsFor(data, snapshot);
  const platforms = data.presentation.platforms.filter(platform => state.arch === 'all' || state.arch === platform.id);
  const suites = data.presentation.suites.filter(suite => (!state.q || `${suite.name} ${suite.description}`.toLowerCase().includes(state.q.toLowerCase()) || rows.some(row => row.test_id === suite.id && row.config_id.toLowerCase().includes(state.q.toLowerCase()))) && (!state.suite || suite.id === state.suite));
  const filtered = suites.filter(suite => !state.status || rows.some(row => row.entry.test_id === suite.id && platforms.some(p => p.id === row.platform.id) && row.current.status === state.status));
  if (!filtered.length) return emptyState('No matching test suites', 'Try another architecture, name, or result filter.', state, { q: null, suite: null, status: null });
  const mobile = `<div class="mobile-coverage-list">${filtered.map(suite => `<article class="mobile-suite"><div class="mobile-suite-title"><strong>${e(suite.name)}${suite.kind === 'build' ? '<span class="tiny-tag">Build only</span>' : ''}</strong><small>${e(suite.description)}</small></div><div class="mobile-suite-platforms">${platforms.map(platform => {
    const cellRows = rows.filter(row => row.entry.test_id === suite.id && row.platform.id === platform.id);
    const summary = summarize(cellRows);
    const label = summary.expected ? `${summary.passed}/${summary.expected} passed${summary.status === 'passed' ? '' : ` · ${statuses[summary.status].label}`}` : 'Not configured';
    const contents = `<span>${e(platform.label)}</span>${badge(summary.status, label)}`;
    return cellRows.length ? link(state, { view: 'tests', arch: platform.id, suite: suite.id, detail: cellRows.length === 1 ? `${suite.id}|${cellRows[0].config_id}` : null, q: null, status: null }, contents, 'mobile-platform-result') : `<div class="mobile-platform-result not-configured">${contents}</div>`;
  }).join('')}</div></article>`).join('')}</div>`;
  return `${mobile}<div class="matrix-scroll"><table class="coverage-matrix ${compact ? 'compact' : ''}"><caption class="sr-only">Test suites by architecture. Fractions show passed over expected configurations. Open a cell for configurations. Unconfigured cells are excluded from the candidate count.</caption><thead><tr><th scope="col">Test suite</th>${platforms.map(platform => `<th scope="col"><span>${e(platform.label)}</span><small>${platform.id === 'tdx' ? 'x86-64 environment' : platform.id === 'loong' ? 'Build only' : platform.id === 'arm' ? 'Boot / build' : 'Runtime tests'}</small></th>`).join('')}</tr></thead><tbody>${filtered.map(suite => `<tr class="${suite.kind === 'build' ? 'build-row' : ''}"><th scope="row"><span class="suite-name">${e(suite.name)}${suite.kind === 'build' ? '<span class="tiny-tag">Build</span>' : ''}</span><small>${e(suite.description)}</small></th>${platforms.map(platform => {
    const cellRows = rows.filter(row => row.entry.test_id === suite.id && row.platform.id === platform.id);
    const summary = summarize(cellRows);
    if (!cellRows.length) return '<td class="unconfigured"><span>—</span><small>Not configured</small></td>';
    const label = summary.passed > 0 ? `${summary.passed}/${summary.expected} passed` : statuses[summary.status]?.label;
    const detail = cellRows.length === 1 ? `${suite.id}|${cellRows[0].config_id}` : null;
    return `<td>${link(state, { view: 'tests', arch: platform.id, suite: suite.id, detail, q: null, status: null }, badge(summary.status, label), 'matrix-cell-link')}${!compact ? `<small>${summary.expected} configurations</small>` : ''}</td>`;
  }).join('')}</tr>`).join('')}</tbody></table></div>`;
}

function legend() {
  return `<div class="matrix-footer"><div class="legend"><span><i class="dot green-dot"></i>Passed</span><span><i class="dot red-dot"></i>Failed / error</span><span><i class="dot blue-dot"></i>Running</span><span><i class="dot amber-dot"></i>Blocked / missing report</span><span><i class="dot gray-dot"></i>Unverified</span></div><span>A build pass does not establish runtime coverage</span></div>`;
}

function sparkline(metric, data, platform, asOf) {
  const points = (data.presentation.history.find(item => item.metric_id === metric.id && item.platform === platform)?.points ?? []).filter(point => point.at <= asOf);
  const values = points.map(point => point.asterinas).filter(value => value != null);
  const min = Math.min(...values), max = Math.max(...values);
  let segments = [], current = [], previousEnvironment = null;
  points.forEach((point, index) => {
    if (point.asterinas == null || (previousEnvironment && previousEnvironment !== point.environment_id)) { if (current.length) segments.push(current.join(' ')); current = []; }
    if (point.asterinas != null) current.push(`${5 + index * 15},${35 - (point.asterinas - min) / (max - min || 1) * 25}`);
    previousEnvironment = point.environment_id;
  });
  if (current.length) segments.push(current.join(' '));
  return `<svg class="sparkline" viewBox="0 0 205 45" aria-hidden="true">${segments.map(segment => `<polyline points="${segment}" fill="none" stroke="currentColor" stroke-width="2"/>`).join('')}</svg>`;
}

function metricCards(data, state, snapshot, limit = 6) {
  const platform = state.arch === 'all' ? 'x86' : state.arch;
  if (!['x86', 'tdx'].includes(platform)) return emptyState('No performance data for this platform yet', 'Test scope and performance measurements are tracked separately. This platform has no benchmark results yet.', state);
  return `<div class="metric-grid">${performanceRows(data, snapshot, platform).slice(0, limit).map(metric => link(state, { view: 'performance', metric: metric.id, detail: null, point: null }, `<div class="metric-category">${e(metric.category)}<span>${icon('arrow')}</span></div><h3>${e(metric.name)}</h3><p>${e(metric.description)}</p><div class="metric-numbers"><strong>${n(metric.asterinas?.value)}<small>${e(metric.unit)}</small></strong><span class="ratio ${metric.ratio == null ? 'gray' : metric.ratio >= 1 ? 'green' : 'amber'}">${metric.ratio == null ? 'Comparison pending' : `${metric.ratio.toFixed(2)}×`}</span></div><div class="metric-comparison">Linux ${n(metric.linux?.value)} ${e(metric.unit)} <span>${metric.direction === 'higher' ? '↑ Higher is better' : '↓ Lower is better'}</span></div>${sparkline(metric, data, platform, snapshot.as_of)}`, `metric-card ${state.metric === metric.id ? 'metric-selected' : ''}`)).join('')}</div>`;
}

export function overview(data, state, snapshot) {
  const rows = rowsFor(data, snapshot, state.arch).filter(row => row.entry.check_kind !== 'performance');
  const concerns = rows.filter(row => !['passed', 'not_selected'].includes(row.current.status)).slice(0, 4);
  return `${pageHeader(data, state, snapshot, 'QUALITY AT A GLANCE', 'Quality starts with evidence.', 'Explore test coverage, Linux API support, and performance across architectures.')}
    ${platformTabs(data, state)}${statCards(rows)}
    <div class="overview-columns"><section class="card matrix-card">${sectionHeader('COVERAGE', 'Coverage across architectures', link(state, { view: 'tests', suite: null, detail: null }, 'View all ' + icon('arrow')))}<p class="section-description">Each cell reflects its configured scope, including gaps and partial results.</p>${matrix(data, state, snapshot, true)}${legend()}</section>
    <aside class="overview-aside"><section class="card attention-card">${sectionHeader('NEEDS ATTENTION', 'Needs attention', `<span class="count-pill">${rows.filter(row => !['passed', 'not_selected'].includes(row.current.status)).length}</span>`)}${concerns.length ? concerns.map(row => link(state, { view: 'tests', detail: `${row.test_id}|${row.config_id}`, suite: null }, `<div class="attention-line">${badge(row.current.status)}<span>${e(row.platform.label)}</span></div><strong>${e(row.entry.label)}</strong><p>${e(row.current.reason)}</p><span class="attention-more">View configuration ${icon('arrow')}</span>`, 'attention-item')).join('') : '<div class="all-clear">' + icon('check') + '<p>No outstanding items in this scope.</p></div>'}</section>
    <section class="scope-note"><span class="scope-note-icon">${icon('info')}</span><h3>Understand the scope.</h3><p>Current main status and the latest available result are shown separately. Historical results retain their original commit and collection time.</p>${link(state, { view: 'methods' }, 'How results are counted ' + icon('arrow'))}</section></aside></div>
    <section class="performance-preview">${sectionHeader('PERFORMANCE', 'Compare measurements with Linux', link(state, { view: 'performance' }, 'All metrics and trends ' + icon('arrow')))}${metricCards(data, state, snapshot, 3)}<p class="footnote">${icon('info')} A ratio above 1 favors Asterinas for that metric. Metrics are not combined into a score. Gaps mark missing data or environment changes.</p></section>
    <section class="card overview-bottom"><div>${icon('code')}<div><h3>Which syscalls can your application use?</h3><p>Explore declarations, flags, and limitations by architecture, with versioned sources.</p></div></div>${link(state, { view: 'api' }, 'Explore API declarations ' + icon('arrow'), 'button secondary')}</section>`;
}

export function tests(data, state, snapshot) {
  const rows = rowsFor(data, snapshot, state.arch).filter(row => row.entry.check_kind !== 'performance');
  const selectedRows = rows.filter(row => (!state.suite || row.test_id === state.suite) && (!state.status || row.current.status === state.status) && (!state.q || `${row.entry.label} ${row.config_id}`.toLowerCase().includes(state.q.toLowerCase())));
  return `${pageHeader(data, state, snapshot, 'TEST COVERAGE', 'What is tested. What is missing.', 'Inspect configurations by architecture and suite, with selection reasons, stages, and evidence.')}${platformTabs(data, state)}
    <div class="filters"><label class="search-field">${icon('search')}<input type="search" data-filter="q" aria-label="Search test suites or configurations" placeholder="Search suites or configurations…" value="${e(state.q ?? '')}"></label><label class="select-field"><span class="sr-only">Filter by result</span><select data-filter="status" aria-label="Filter by result"><option value="">All results</option>${Object.entries(statuses).filter(([key]) => key !== 'not_configured').map(([key, value]) => `<option value="${key}" ${state.status === key ? 'selected' : ''}>${value.label}</option>`).join('')}</select></label>${state.suite ? `<span class="filter-chip">${e(data.presentation.suites.find(s => s.id === state.suite)?.name ?? state.suite)}${link(state, { suite: null, detail: null }, icon('cross'), 'clear-filter')}</span>` : ''}<span class="filter-count">${selectedRows.length} / ${rows.length} configurations</span></div>
    <section class="card">${matrix(data, state, snapshot)}${legend()}</section>
    ${sectionHeader('CONFIGURATIONS', state.suite ? 'Suite configurations' : 'Configurations and execution records', '<span class="muted">Open a record to inspect its evidence</span>')}
    ${selectedRows.length ? `<section class="card table-scroll"><table class="data-table"><thead><tr><th>Test / configuration</th><th>Platform</th><th>Current commit</th><th>Latest available result</th><th>Selection / scope</th><th></th></tr></thead><tbody>${selectedRows.map(row => `<tr><td><a data-route class="row-title" href="${e(href(state, { detail: `${row.test_id}|${row.config_id}` }))}">${e(row.entry.label)}</a><small class="mono">${e(row.config_id)}</small></td><td>${e(row.platform.label)}<small>SMP ${row.entry.config.smp} · ${e(row.entry.config.profile)}</small></td><td>${badge(row.current.status)}<small class="mono">${shortSHA(snapshot.main_sha)}</small></td><td>${row.latest_result ? `${badge(row.latest_result.outcome)}<small><code>${shortSHA(row.latest_result.source_sha)}</code> · ${formatTime(row.latest_result.collected_at)}${row.entry.cadence === 'daily' && resultAge(row.latest_result.collected_at).stale ? ' · Stale' : ''}</small>` : '<span class="muted">No result yet</span>'}</td><td><span class="selection-text">${row.current.selection === 'selected' ? 'Selected' : 'Not selected'}</span><small>${row.entry.check_kind === 'build' ? 'Build check only' : row.entry.config.filesystem !== 'none' ? e(row.entry.config.filesystem) : 'Runtime tests'}</small></td><td>${link(state, { detail: `${row.test_id}|${row.config_id}` }, icon('chevron'), 'table-open')}</td></tr>`).join('')}</tbody></table></section>` : emptyState('No matching configurations', 'No execution records match these filters. Unconfigured cells remain in the matrix above.', state, { q: null, status: null, suite: null })}`;
}

export function api(data, state, snapshot) {
  const declaration = data.byID.get(snapshot.api_declarations_id);
  const platform = data.presentation.platforms.find(p => p.id === state.arch);
  const arch = platform?.arch ?? 'x86_64';
  const entries = declaration.entries.filter(entry => entry.arch === arch);
  const filtered = entries.filter(entry => (!state.q || `${entry.name} ${entry.flags.map(flag => flag.name).join(' ')}`.toLowerCase().includes(state.q.toLowerCase())) && (!state.status || entry.status === state.status) && (!state.category || entry.category === state.category));
  const categories = [...new Set(entries.map(entry => entry.category))];
  return `${pageHeader(data, state, snapshot, 'LINUX API DECLARATIONS', 'Support, with clear boundaries.', 'Find declared support for syscalls, parameters, and flags. Runtime evidence is tracked separately.')}${platformTabs(data, state)}
    <div class="notice info-notice">${icon('book')}<div><strong>API support declarations · ${e(platform?.label ?? 'x86-64')} · source ${shortSHA(declaration.source_sha)}</strong><p>A fictional subset of ${entries.length} declarations; not an overall Linux compatibility rate. API-to-case mapping is not available in this preview.</p></div></div>
    <div class="api-stat-grid">${Object.entries(apiStatuses).map(([key, value]) => `<div class="api-stat ${value.tone}"><span>${value.label}</span><strong>${entries.filter(entry => entry.status === key).length}</strong></div>`).join('')}</div>
    <div class="filters"><label class="search-field">${icon('search')}<input data-filter="q" type="search" aria-label="Search syscalls or flags" placeholder="Search syscalls or flags, e.g. mmap…" value="${e(state.q ?? '')}"></label><select data-filter="category" aria-label="API category"><option value="">All categories</option>${categories.map(category => `<option ${state.category === category ? 'selected' : ''}>${e(category)}</option>`).join('')}</select><select data-filter="status" aria-label="API support status"><option value="">All support states</option>${Object.entries(apiStatuses).map(([key, value]) => `<option value="${key}" ${state.status === key ? 'selected' : ''}>${value.label}</option>`).join('')}</select><span class="filter-count">${filtered.length} declarations</span></div>
    ${filtered.length ? `<section class="card api-list"><div class="api-table-heading"><span>SYSCALL / CATEGORY</span><span>Support status</span><span>LIMITATIONS & FLAGS</span></div>${filtered.map(entry => `<details class="api-entry" ${state.api === entry.api_id ? 'open' : ''} data-api="${e(entry.api_id)}"><summary><span><code>${e(entry.name)}</code><small>${e(entry.category)}</small></span><span>${apiBadge(entry.status)}</span><span class="api-limitation">${e(entry.limitations[0] ?? 'No additional limitations in this example')}<small>${entry.flags.length ? `${entry.flags.length} flags · partial inventory` : 'Flags not assessed'}</small></span>${icon('chevron')}</summary><div class="api-expanded"><div class="api-expanded-heading"><strong>Parameters & flags</strong><span>Architecture ${e(entry.arch)} · Number unverified</span></div>${entry.flags.length ? `<div class="flag-list">${entry.flags.map(flag => `<div><code>${e(flag.name)}</code>${apiBadge(flag.status)}<span>${e(flag.limitations.join('; ') || 'No additional limitations in this example')}</span></div>`).join('')}</div>` : '<p class="muted">An empty flag list does not imply full support; detailed flags have not been assessed.</p>'}<div class="source-line">${icon('file')} Source version <code>${shortSHA(declaration.source_sha)}</code> · <span>${e(entry.sources[0].path)}</span></div><div class="api-evidence">Runtime evidence: no explicit API-to-case mapping yet.${link(state, { view: 'methods', api: null, q: null, status: null, category: null }, 'Declarations and runtime evidence ' + icon('arrow'))}</div></div></details>`).join('')}</section>` : emptyState(entries.length ? 'No matching API declarations' : 'No declarations for this architecture yet', entries.length ? 'Try another name, flag, or support state.' : 'x86-64 syscall numbers and support conclusions are not applied to this architecture.', state, entries.length ? { q: null, status: null, category: null } : null)}`;
}

function trendChart(points, metric, selectedIndex) {
  const width = 880, height = 266, left = 68, right = 24, top = 38, bottom = 40;
  const values = points.flatMap(point => [point.asterinas, point.linux]).filter(value => value != null);
  const min = Math.min(...values) * 0.92, max = Math.max(...values) * 1.06;
  const x = index => left + index * (width - left - right) / Math.max(1, points.length - 1);
  const y = value => top + (max - value) / (max - min || 1) * (height - top - bottom);
  const changedIndex = points.findIndex((point, index) => index && point.environment_id !== points[index - 1].environment_id);
  const systemLines = ['asterinas', 'linux'].map(system => {
    const segments = []; let current = [];
    points.forEach((point, index) => {
      if (point[system] == null || (index && point.environment_id !== points[index - 1].environment_id)) { if (current.length) segments.push(current); current = []; }
      if (point[system] != null) current.push(`${x(index)},${y(point[system])}`);
    });
    if (current.length) segments.push(current);
    return segments.map(segment => `<polyline points="${segment.join(' ')}" fill="none" stroke="${system === 'asterinas' ? '#267a66' : '#8796aa'}" stroke-width="2.6" stroke-linecap="round"/>`).join('');
  }).join('');
  return `<svg id="trend-chart" class="trend-chart" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="chart-title chart-desc"><title id="chart-title">${e(metric.name)} historical Linux and Asterinas measurements</title><desc id="chart-desc">Lines break at missing data and environment changes. Focus a data point or expand the data table below.</desc><rect width="${width}" height="${height}" fill="white"/>${changedIndex > 0 ? `<rect x="${x(changedIndex) - 12}" y="${top - 12}" width="${width - x(changedIndex) - 12}" height="${height - top - bottom + 12}" fill="#f0f7f2"/><line x1="${x(changedIndex) - 12}" x2="${x(changedIndex) - 12}" y1="${top - 12}" y2="${height - bottom}" stroke="#c7d8cd" stroke-dasharray="4 5"/><text x="${x(changedIndex) + 1}" y="19" fill="#6b8773" font-size="11">Environment B · new segment</text>` : ''}${Array.from({ length: 5 }, (_, index) => { const value = min + (max - min) * index / 4; return `<line x1="${left}" x2="${width - right}" y1="${y(value)}" y2="${y(value)}" stroke="#edf0ee"/><text x="${left - 12}" y="${y(value) + 4}" text-anchor="end" fill="#8b9692" font-size="11">${n(value)}</text>`; }).join('')}${systemLines}${points.map((point, index) => `${index % (points.length > 8 ? 2 : 1) === 0 || index === points.length - 1 ? `<text x="${x(index)}" y="${height - 12}" text-anchor="middle" fill="#8b9692" font-size="11">${formatDate(point.at)}</text>` : ''}${point.asterinas != null ? `<circle class="chart-point ${selectedIndex === index ? 'point-selected' : ''}" data-point="${index}" cx="${x(index)}" cy="${y(point.asterinas)}" r="5" fill="#267a66" stroke="white" stroke-width="2" tabindex="0" role="button" aria-label="${formatDate(point.at)}, Asterinas ${n(point.asterinas)} ${e(metric.unit)}, Linux ${n(point.linux)} ${e(metric.unit)}"><title>${formatDate(point.at)} · ${n(point.asterinas)} ${e(metric.unit)}</title></circle>` : ''}`).join('')}<text x="${left}" y="19" fill="#87958d" font-size="11">${e(metric.unit)}</text></svg>`;
}

export function performance(data, state, snapshot) {
  const platform = state.arch === 'all' ? 'x86' : state.arch;
  const header = `${pageHeader(data, state, snapshot, 'PERFORMANCE IN CONTEXT', 'Measurements in context.', 'Compare workloads with Linux, inspect methods, and track history within comparable environments.')}${platformTabs(data, state)}`;
  if (!['x86', 'tdx'].includes(platform)) return header + emptyState('No benchmarks for this platform yet', 'No benchmark data is available for the selected architecture.', state);
  const metrics = performanceRows(data, snapshot, platform);
  const metric = metrics.find(item => item.id === state.metric) ?? metrics[0];
  const fullHistory = data.presentation.history.find(item => item.platform === platform && item.metric_id === metric.id)?.points ?? [];
  const points = fullHistory.filter(point => point.at <= snapshot.as_of).slice(state.range === '7' ? -7 : -14);
  const selectedIndex = Math.min(Number(state.point ?? points.length - 1), points.length - 1);
  const selected = points[selectedIndex];
  return `${header}<div class="performance-intro"><p><span class="status-dot"></span>${platform === 'tdx' ? 'Intel TDX' : 'x86-64 / QEMU'} · Fixed representative metrics and configurations</p><span>Original measurements · no combined score</span></div>${metricCards(data, { ...state, metric: metric.id }, snapshot)}
    <section class="card trend-card"><div class="section-heading"><div><div class="eyebrow">METRIC DETAIL</div><h2>${e(metric.name)} <span class="unit-pill">${e(metric.unit)}</span></h2><p class="section-description">${e(metric.description)} · ${metric.direction === 'higher' ? 'Higher is better' : 'Lower is better'}</p></div><div class="chart-actions"><div class="segmented">${['7', '14'].map(range => link(state, { range, point: null }, `${range} days`, state.range === range || !state.range && range === '14' ? 'selected' : '')).join('')}</div><button class="icon-button" data-download="chart" aria-label="Download trend SVG">${icon('download')}</button></div></div>
    <div class="comparison-strip"><div><span class="series-dot asterinas-dot"></span><span>Asterinas</span><strong>${n(metric.asterinas?.value)} <small>${e(metric.unit)}</small></strong></div><div><span class="series-dot linux-dot"></span><span>Linux</span><strong>${n(metric.linux?.value)} <small>${e(metric.unit)}</small></strong></div><div class="comparison-ratio">${metric.ratio == null ? '<span class="muted">Comparison pending</span>' : `<strong class="${metric.ratio >= 1 ? 'green-text' : 'amber-text'}">${metric.ratio.toFixed(2)}×</strong><span>${metric.direction === 'higher' ? 'Asterinas / Linux' : 'Linux / Asterinas'}</span>`}</div><span class="comparison-explanation">${e(metric.comparisonReason)}</span></div>
    ${points.length ? trendChart(points, metric, selectedIndex) : '<p class="notice">No historical points are available for this snapshot.</p>'}
    <div class="chart-readout" aria-live="polite">${selected ? `<span>${icon('clock')} ${formatTime(selected.at)}</span><code>${shortSHA(selected.source_sha)}</code><span>Asterinas <strong>${n(selected.asterinas)}</strong> / Linux <strong>${n(selected.linux)}</strong> ${e(metric.unit)}</span><span class="readout-env">${e(selected.environment_id)} · ${e(selected.method_version)}</span>` : ''}</div>
    <details class="equivalent-table"><summary>${icon('layers')} View chart data table <span>${points.length} samples</span></summary><div class="table-scroll"><table class="data-table"><thead><tr><th>Time</th><th>Commit</th><th>Asterinas (${e(metric.unit)})</th><th>Linux (${e(metric.unit)})</th><th>Environment / method</th></tr></thead><tbody>${points.map(point => `<tr><td>${formatTime(point.at)}</td><td><code>${shortSHA(point.source_sha)}</code></td><td>${n(point.asterinas)}</td><td>${n(point.linux)}</td><td>${e(point.environment_id)}<small>${e(point.method_version)}</small></td></tr>`).join('')}</tbody></table></div></details></section>
    <div class="two-columns"><section class="card detail-card">${sectionHeader('METHOD', 'Method and selection rationale')}<p>${e(metric.reason)}</p><dl class="key-values"><div><dt>Metric ID</dt><dd><code>${e(metric.id)}</code></dd></div><div><dt>Method version</dt><dd>demo-paired-v1</dd></div><div><dt>Workload</dt><dd>Fixed request count, concurrency, and virtual devices</dd></div><div><dt>Collected at</dt><dd>${formatTime(metric.report?.collected_at)}</dd></div></dl><p class="footnote">Missing values remain missing. Summary metrics are kept even when results are incomplete or slower.</p></section><section class="card detail-card">${sectionHeader('ENVIRONMENT', 'Environment and comparability')}<dl class="key-values"><div><dt>CPU / vCPU</dt><dd>Xeon Gold 6430 · 8 vCPU (example)</dd></div><div><dt>Memory / VM</dt><dd>8192 MiB · QEMU 9.2 (example)</dd></div><div><dt>Reference kernel</dt><dd>Linux 6.12 · digest recorded (example)</dd></div><div><dt>Environment changes</dt><dd>Environment A → B; segments are not connected</dd></div></dl><p class="footnote">Only system kernel and dedicated boot-parameter differences declared by the method are allowed.</p></section></div>
    ${sectionHeader('ALL METRICS', 'All metrics', '<span class="muted">Includes missing and slower results</span>')}<section class="card table-scroll"><table class="data-table"><thead><tr><th>Metric / fixed configuration</th><th>Asterinas</th><th>Linux</th><th>Direction</th><th>Comparison</th></tr></thead><tbody>${metrics.map(item => `<tr><td>${link(state, { metric: item.id, point: null }, e(item.name), 'row-title')}<small class="mono">${e(item.id)} · ${e(platform)}-release-smp8</small></td><td>${n(item.asterinas?.value)} <span class="muted">${e(item.unit)}</span></td><td>${n(item.linux?.value)} <span class="muted">${e(item.unit)}</span></td><td>${item.direction === 'higher' ? '↑ Higher is better' : '↓ Lower is better'}</td><td>${item.ratio == null ? badge('unknown', 'Linux measurement missing') : `<strong class="${item.ratio >= 1 ? 'green-text' : 'amber-text'}">${item.ratio.toFixed(2)}×</strong>`}</td></tr>`).join('')}</tbody></table></section>`;
}

export function methods(data, state, snapshot) {
  const counts = countRows(rowsFor(data, snapshot).filter(row => row.entry.check_kind !== 'performance'));
  return `${pageHeader(data, state, snapshot, 'METHODS & DATA', 'Every result has a source.', 'Understand counting rules, data sources, freshness, retention, and the scope of this preview.')}
    <section class="methods-hero"><div class="eyebrow">EVIDENCE → CONTEXT → CONCLUSION</div><h2>Scope. Identity. Configuration. Evidence.<br><span>Missing evidence stays unknown.</span></h2><p>A pass applies to a specific commit, configuration, and executed scope. Declarations cite sources, measurements record environments, and history retains its original context.</p><span class="methods-star" aria-hidden="true">✳</span></section>
    <div class="two-columns"><section class="card detail-card">${sectionHeader('COUNTING', 'Reading scope and status')}<div class="formula"><strong>${counts.expected}</strong> expected <span>=</span> <strong class="green-text">${counts.passed}</strong> passed <span>+</span> <strong class="red-text">${counts.failed}</strong> failed <span>+</span> <strong class="amber-text">${counts.unresolved}</strong> unresolved</div><p>Candidates come from the inventory before selection. Unselected, cancelled, errored, and missing results do not reduce the denominator. Test counts include build checks, exclude benchmarks, and do not represent an overall compatibility rate.</p><div class="method-rule"><strong>Current commit ≠ latest available result</strong><p>A commit without a current result remains unverified. Historical passes retain their original SHA and collection time.</p></div><div class="method-rule"><strong>Support declaration ≠ runtime evidence</strong><p>Book/SCML declarations and flag scope are shown separately. SCML checks do not establish runtime verification.</p></div></section>
    <section class="card detail-card">${sectionHeader('FRESHNESS', 'Freshness, updates, and retention')}<dl class="key-values"><div><dt>Update target</dt><dd>Report first available → publicly visible within 30 minutes</dd></div><div><dt>Daily results</dt><dd>Marked stale after 48 hours from collection</dd></div><div><dt>Historical summaries</dt><dd>Retained for at least 90 days; referenced records are kept</dd></div><div><dt>Original logs</dt><dd>30-day retention requested; actual expiry is displayed</dd></div><div><dt>Unknown timestamps</dt><dd>Preserve null; first discovery is not first availability</dd></div></dl><p class="footnote">These are design targets. Live CI ingestion, publication receipts, and historical retention are not connected in this preview.</p></section></div>
    <section class="card data-flow-card">${sectionHeader('DATA JOURNEY', 'From execution facts to the page')}<div class="data-flow">${[['01', 'CI execution facts', 'Configurations, plans, stages, and original outcomes'], ['02', 'Adaptation and collection', 'Reports, platform observations, and identity checks'], ['03', 'Canonical records and snapshots', 'Complete scope, history, and gaps'], ['04', 'Static page', 'Accessible views and public visibility']].map(([number, title, description]) => `<div><span>${number}</span><strong>${title}</strong><p>${description}</p></div>`).join('')}</div><p class="footnote">QA consumes CI facts. Page or collection failures do not alter CI execution, cancellation, or test outcomes.</p></section>
    <section class="card detail-card">${sectionHeader('PREVIEW DATA', 'Preview data and scope', '<button class="button secondary" data-download="data">' + icon('download') + ' Download demo records</button>')}<div class="two-columns no-gap"><div><h3>Compatible record structure</h3><p>The demo uses v1.0 catalog, plan, report, api_declarations, and snapshot records. All records are marked <code>example=true</code>, with fictional repositories and commits. Separate presentation metadata supplies groups, case examples, and chart history.</p><p>Production CI facts will be mapped by a host adapter. Schema 1.1 provenance for partial reruns is outside this preview.</p></div><div><h3>What to explore</h3><p>Switch snapshots and architectures, open failed or blocked configurations, compare current and historical results, search syscalls and flags, and inspect missing measurements and segmented trends.</p><p>Execution and evidence links open local examples with explicitly fictional identities. ${link(state, { view: 'tests', status: 'failed', arch: 'all' }, 'Explore failure examples ' + icon('arrow'))}</p></div></div><div class="source-line">${icon('file')} Data generated ${formatTime(data.snapshots[0].generated_at)} · ${data.reports.length} fictional reports · ${data.snapshots.length} snapshots · <a href="./data/demo.json" target="_blank" rel="noopener">Raw JSON</a> · <a href="./data/schema-v1.json" target="_blank" rel="noopener">JSON Schema</a></div></section>`;
}

function stageFlow(row) {
  const gates = row.current.observation?.gate_observations ?? [];
  const blockedBy = gates.filter(gate => gate.state !== 'passed').map(gate => gate.gate_id);
  const stage = name => `<span class="stage ${gates.some(gate => gate.gate_id.endsWith(`/${name}`) && gate.state === 'failed') ? 'stage-failed' : ''}">${icon(name.startsWith('suite') ? 'tests' : 'layers')}${e(name)}</span>`;
  const arrow = '<span class="stage-separator" aria-hidden="true">→</span>';
  let flow, description;
  if (row.test_id === 'nixos') {
    flow = `${stage('suite.build')}${arrow}${stage('suite.test')}`;
    description = 'Each selected suite builds its own image, then runs its original driver. Suites run in parallel without a shared ready gate.';
  } else if (row.entry.check_kind === 'build') {
    flow = stage('smoke.compile');
    description = 'Build check only. This result does not establish boot or runtime test coverage.';
  } else {
    flow = `<div class="parallel-stages"><div class="parallel-label">Shared prerequisites · parallel</div><div>${stage('smoke.lint')}</div><div>${stage('smoke.compile')}${arrow}${stage('smoke.boot')}</div></div>`;
    if (row.test_id !== 'boot') {
      flow += `${arrow}<div class="suite-stages">${row.test_id === 'kernel/ktest' ? `${stage('suite.build')}${arrow}` : ''}${stage('suite.test')}</div>`;
    }
    description = row.test_id === 'boot' ? 'lint ∥ (compile → boot). Compile and boot share one job; shared prerequisites count once per execution.' : 'Suites run in parallel after lint ∥ (compile → boot) all succeed. Both ktest build and execution follow this gate.';
  }
  return `<div class="stage-flow">${flow}</div><p class="footnote">${description}</p>${blockedBy.length ? `<div class="notice warning-notice">${icon('lock')} blocked_by: <code>${e(blockedBy.join(', '))}</code></div>` : ''}`;
}

export function testDetail(data, state, snapshot) {
  const row = rowsFor(data, snapshot).find(item => `${item.test_id}|${item.config_id}` === state.detail);
  if (!row) return `<div class="dialog-header"><h2 id="detail-title">Configuration not found</h2><button data-close-dialog class="icon-button" aria-label="Close details">${icon('cross')}</button></div><p class="notice">This configuration is not present in the selected snapshot. Choose another configuration.</p>`;
  const group = data.presentation.groups[state.detail];
  const config = row.entry.config;
  const plan = data.byID.get(row.current.plan_id)?.entries.find(entry => entry.test_id === row.test_id && entry.config_id === row.config_id);
  const cases = data.presentation.cases[row.report?.record_id] ?? [];
  const execution = row.report?.execution ?? row.current.observation?.execution;
  const scenarios = row.test_id === 'nixos' ? `<section class="detail-section"><h3>Application scenarios and assertion scope</h3><div class="scenario-list">${[['NGINX', 'Start service → read a fixed page over HTTP → stop service', 'Does not establish coverage for TLS, proxying, or other workloads.'], ['SQLite', 'Create a table, insert records, and query with a condition', 'Does not establish complete SQL, transaction, or durability coverage.'], ['Firefox', 'Open a site headlessly and check that a screenshot file exists', 'No GUI window is tested; this is not GUI coverage.'], ['OpenJDK', 'Selected openjdk21 jtreg subset', 'Preserves subset scope and exclusions; does not imply full certification.']].map(([name, assertion, boundary]) => `<article><strong>${name}</strong><p>${assertion}</p><small>${boundary}</small></article>`).join('')}</div><p class="footnote">These scenarios illustrate how scope is described. All outcomes shown here remain fictional.</p></section>` : '';
  return `<div class="dialog-header"><div><div class="eyebrow">SUITE / CONFIGURATION</div><h2 id="detail-title">${e(row.entry.label)} <span>${e(row.platform.label)}</span></h2></div><button data-close-dialog class="icon-button" aria-label="Close details">${icon('cross')}</button></div><div class="dialog-body"><code class="config-title">${e(row.config_id)}</code><div class="detail-status">${badge(row.current.status)}<span>Target main <code>${shortSHA(snapshot.main_sha)}</code></span></div><p class="detail-reason">${e(row.current.reason)}</p>
    <section class="detail-section"><h3>Current and latest results</h3><div class="current-vs-latest"><div><span>Current commit</span><strong>${statuses[row.current.status]?.label ?? 'Unknown'}</strong><code>${shortSHA(snapshot.main_sha)}</code><small>${row.report ? formatTime(row.report.collected_at) : 'No qualifying complete result yet'}</small></div><div><span>Latest available result</span><strong>${row.latest_result ? statuses[row.latest_result.outcome].label : 'No result yet'}</strong><code>${shortSHA(row.latest_result?.source_sha)}</code><small>${formatTime(row.latest_result?.collected_at)}${row.entry.cadence === 'daily' && resultAge(row.latest_result?.collected_at).stale ? ' · Stale' : ''}</small></div></div></section>
    <section class="detail-section"><h3>Stages and dependencies</h3><code class="group-label">${e(group?.group ?? 'Group not recorded')}</code>${stageFlow(row)}</section>
    ${scenarios}<section class="detail-section"><h3>Effective configuration</h3><dl class="key-values"><div><dt>Architecture / platform</dt><dd>${e(config.arch)} / ${e(config.platform)}</dd></div><div><dt>Profile / SMP / memory</dt><dd>${e(config.profile)} · ${config.smp} vCPU · ${config.mem_mib} MiB</dd></div><div><dt>Boot / filesystem</dt><dd>${e(config.boot_protocol)} / ${e(config.filesystem)}</dd></div><div><dt>Selection</dt><dd>${row.current.selection === 'selected' ? 'Selected' : 'Not selected'} · ${e(plan?.reason_code ?? 'unknown')}</dd></div></dl><div class="parameter-list">${Object.entries(config.parameters).map(([key, value]) => `<code>${e(key)}=${e(value)}</code>`).join('')}</div><details class="raw-details"><summary>View configuration digest</summary><code>${e(row.entry.config_digest)}</code></details></section>
    <section class="detail-section"><h3>Identity, timestamps, and evidence</h3><dl class="key-values"><div><dt>Source SHA</dt><dd><code>${e(execution?.source_sha ?? 'Unknown')}</code></dd></div><div><dt>Tested SHA</dt><dd><code>${e(row.report?.execution.tested_sha ?? 'Unknown; no complete report')}</code></dd></div><div><dt>Run / Attempt / Job</dt><dd>#${e(execution?.run_id)} / ${e(execution?.attempt)} / ${e(row.report?.job_id ?? row.current.observation?.job_id)}</dd></div><div><dt>Execution / report</dt><dd>${e(row.current.execution)} / ${e(row.current.report_state)}</dd></div><div><dt>Environment</dt><dd>${row.report ? e(row.report.environment.cpu_model) : 'Report unavailable; environment cannot be inferred from the platform label'}</dd></div><div><dt>Completeness</dt><dd>${row.report?.result_complete ? 'result_complete=true (example)' : 'Complete pass evidence is unavailable'}</dd></div></dl><div class="detail-actions">${row.report ? `<button class="button secondary" data-download-report="${e(row.report.record_id)}">${icon('download')} Download example report</button>` : ''}<a class="button secondary" href="./data/boot-example.log" target="_blank" rel="noopener">${icon('file')} View example log</a></div><p class="footnote">Run identities and evidence are fictional. This sample log demonstrates the entry point; it is not an actual Actions log for this suite.</p></section>
    ${row.report?.case_summary ? `<section class="detail-section"><h3>Native case summary</h3><div class="case-summary"><span>${row.report.case_summary.expected} expected</span><span class="green-text">${row.report.case_summary.passed} passed</span><span class="red-text">${row.report.case_summary.failed} failed</span></div><p class="footnote">${e(row.report.case_summary.scope)} Showing only ${cases.length} example names below, not the complete case list.</p><div class="case-list">${cases.map(item => `<div><code>${e(item.name)}</code>${badge(item.status)}<small>${e(item.duration)}</small></div>`).join('')}</div></section>` : ''}</div>`;
}
