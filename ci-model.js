// SPDX-License-Identifier: MPL-2.0

export const executionRecord = (data, id) => data.main_results?.records.find(record => record.id === id);
export const suiteCategory = suite => suite.startsWith('nixos/') ? 'nixos' : suite;
export const coverageResults = (data, state = {}) => (data.main_results?.results ?? []).map(result => ({
  ...result, latest: executionRecord(data, result.latest), previousSuccess: executionRecord(data, result.previous_success),
})).filter(result => (!state.arch || state.arch === 'all' || result.platform === state.arch)
  && (!state.suite || suiteCategory(result.suite) === state.suite || result.suite === state.suite)
  && (!state.subsuite || result.suite === state.subsuite)
  && (!state.status || result.latest.conclusion === state.status)
  && (!state.q || `${result.latest.name} ${result.latest.workflow_name} ${result.latest.command ?? ''}`.toLowerCase().includes(state.q.toLowerCase())));

export function workflowGroups(data) {
  const groups = [
    { id: 'failed', label: 'Failed', tone: 'red', workflows: [] },
    { id: 'succeeded', label: 'Succeeded', tone: 'green', workflows: [] },
    { id: 'other', label: 'Other outcomes', tone: 'amber', workflows: [] },
    { id: 'unobserved', label: 'No eligible main run', tone: 'gray', workflows: [] },
  ];
  for (const workflow of data.main_results.workflows) {
    const conclusion = workflow.latest?.conclusion;
    const id = !workflow.latest ? 'unobserved' : conclusion === 'success' ? 'succeeded'
      : ['failure', 'timed_out', 'startup_failure'].includes(conclusion) ? 'failed' : 'other';
    groups.find(group => group.id === id).workflows.push(workflow);
  }
  for (const group of groups) group.workflows.sort((a, b) => a.name.trim().localeCompare(b.name.trim()));
  return groups;
}
