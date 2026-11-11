// SPDX-License-Identifier: MPL-2.0

export const statuses = {
  passed: { label: 'Passed', tone: 'green', symbol: 'check' },
  failed: { label: 'Failed', tone: 'red', symbol: 'cross' },
  error: { label: 'Execution error', tone: 'red', symbol: 'alert' },
  running: { label: 'Running', tone: 'blue', symbol: 'activity' },
  queued: { label: 'Queued', tone: 'blue', symbol: 'clock' },
  cancelled: { label: 'Cancelled', tone: 'gray', symbol: 'slash' },
  blocked: { label: 'Blocked', tone: 'amber', symbol: 'lock' },
  missing_report: { label: 'Missing report', tone: 'amber', symbol: 'file' },
  not_selected: { label: 'Not selected', tone: 'gray', symbol: 'minus' },
  not_triggered: { label: 'Not triggered', tone: 'gray', symbol: 'minus' },
  skipped: { label: 'Skipped', tone: 'gray', symbol: 'minus' },
  unknown: { label: 'Unverified', tone: 'gray', symbol: 'clock' },
  not_configured: { label: 'Not configured', tone: 'muted', symbol: 'minus' },
  configuration_mismatch: { label: 'Configuration mismatch', tone: 'amber', symbol: 'alert' },
};

export const apiStatuses = {
  supported: { label: 'Supported', tone: 'green' },
  partial: { label: 'Partial support', tone: 'amber' },
  unsupported: { label: 'Unsupported', tone: 'gray' },
  not_assessed: { label: 'Not assessed', tone: 'muted' },
};

export const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
export const shortSHA = value => value?.slice(0, 7) ?? 'Unknown';
export const formatNumber = value => value == null ? '—' : new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value);
export const formatTime = value => value ? new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value)) : 'Unknown';
export const formatDate = value => value ? new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(new Date(value)) : '—';

export function resultAge(value, now = Date.now()) {
  if (!value) return { label: 'No result', stale: false };
  const hours = Math.max(0, (now - new Date(value).getTime()) / 3600000);
  return { label: hours < 1 ? `${Math.floor(hours * 60)} min ago` : hours < 24 ? `${Math.floor(hours)} h ago` : `${Math.floor(hours / 24)} d ago`, stale: hours > 48 };
}

export async function loadData() {
  const demo = new URLSearchParams(location.search).get('dataset') === 'demo';
  const response = await fetch(new URL(demo ? './data/demo.json' : './data/real.json', import.meta.url));
  if (!response.ok) throw new Error(`Failed to load snapshot (HTTP ${response.status})`);
  const data = await response.json();
  if (!demo) {
    if (data.format !== 'qa-observations-v1' || data.mode !== 'real' || !data.main_results?.workflows?.length
      || !Array.isArray(data.main_results.records) || !Array.isArray(data.main_results.results) || !data.sources?.length) {
      throw new Error('The public source dataset has an unsupported format or is incomplete.');
    }
    return data;
  }
  const records = ['catalogs', 'plans', 'reports', 'api_declarations', 'snapshots'].flatMap(kind => data[kind] ?? []);
  if (!records.length || records.some(record => record.schema_version !== '1.0' || record.example !== true)) {
    throw new Error('This preview only accepts v1.0 demo records explicitly marked example=true.');
  }
  const byID = new Map(records.map(record => [record.record_id, record]));
  return { ...data, byID };
}

export function snapshotFor(data, state) {
  return data.snapshots.find(snapshot => snapshot.main_sha === state.snapshot) ?? data.snapshots[0];
}

export function platformFor(data, config) {
  return data.presentation.platforms.find(platform => platform.arch === config.arch && platform.platform === config.platform);
}

export function rowsFor(data, snapshot, arch = 'all') {
  const catalog = data.byID.get(snapshot.catalog_id);
  const entries = new Map(catalog.entries.map(entry => [`${entry.test_id}|${entry.config_id}`, entry]));
  return snapshot.rows.map(row => {
    const entry = entries.get(`${row.test_id}|${row.config_id}`);
    return { ...row, entry, platform: platformFor(data, entry.config), report: data.byID.get(row.current.report_id), latest: data.byID.get(row.latest_result?.report_id) };
  }).filter(row => arch === 'all' || row.platform.id === arch);
}

export function countRows(rows) {
  const passed = rows.filter(row => row.current.status === 'passed').length;
  const failed = rows.filter(row => row.current.status === 'failed').length;
  return { expected: rows.length, selected: rows.filter(row => row.current.selection === 'selected').length, received: rows.filter(row => row.report).length, passed, failed, unresolved: rows.length - passed - failed };
}

export function summarize(rows) {
  if (!rows.length) return { status: 'not_configured', passed: 0, expected: 0 };
  const { passed, expected } = countRows(rows);
  const order = ['failed', 'error', 'configuration_mismatch', 'missing_report', 'blocked', 'cancelled', 'running', 'queued', 'unknown', 'not_selected', 'skipped', 'not_triggered'];
  const status = order.find(value => rows.some(row => row.current.status === value)) ?? 'passed';
  return { status, passed, expected };
}

export function comparisonFor(report, metricID) {
  const asterinas = report?.measurements.find(item => item.metric_id === metricID && item.system === 'asterinas');
  const linux = report?.measurements.find(item => item.metric_id === metricID && item.system === 'linux');
  const base = { asterinas, linux, ratio: null, status: 'unknown', reason: 'Complete measurements for both systems are not available.' };
  if (!asterinas || !linux || [asterinas, linux].some(item => item.state !== 'measured' || !Number.isFinite(item.value))) return base;
  if (report.environment.unresolved_fields.length) return { ...base, reason: 'Environment details are incomplete.' };
  if (asterinas.comparison_group !== linux.comparison_group || asterinas.unit !== linux.unit || asterinas.direction !== linux.direction || asterinas.method_version !== linux.method_version) return { ...base, status: 'incomparable', reason: 'Measurement groups, units, or methods differ.' };
  const numerator = asterinas.direction === 'higher' ? asterinas.value : linux.value;
  const denominator = asterinas.direction === 'higher' ? linux.value : asterinas.value;
  return denominator > 0 ? { ...base, ratio: numerator / denominator, status: 'comparable', reason: 'Matching measurement group, configuration, and method; environment details are complete.' } : { ...base, reason: 'The ratio denominator must be positive.' };
}

export function performanceRows(data, snapshot, platform = 'x86') {
  const row = rowsFor(data, snapshot, platform).find(item => item.entry.check_kind === 'performance');
  return data.presentation.metrics.map(metric => {
    const { reason, ...comparison } = comparisonFor(row?.report, metric.id);
    return { ...metric, report: row?.report, ...comparison, comparisonReason: reason };
  });
}

export function href(state, patch = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries({ ...state, ...patch })) {
    if (value != null && value !== '' && !(key === 'view' && value === 'overview') && !(key === 'arch' && value === 'all') && !(key === 'snapshot' && value === 'latest')) params.set(key, value);
  }
  return `./${params.size ? `?${params}` : ''}`;
}
