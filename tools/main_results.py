# SPDX-License-Identifier: MPL-2.0
"""Collect main-only Actions observations and retain per-job execution history."""

import concurrent.futures
import json
import re
import subprocess

EVENTS = frozenset(("push", "schedule", "workflow_dispatch"))
HISTORY_LIMIT = 20


def eligible(run, repository, branch="main"):
    return (run.get("status") == "completed" and run.get("head_branch") == branch
            and run.get("event") in EVENTS
            and (run.get("head_repository") or {}).get("full_name") == repository)


def category(path):
    name = path.rsplit("/", 1)[-1]
    for prefix, label in (("test_", "Tests"), ("benchmark_", "Benchmarks"),
                          ("check_", "Checks"), ("validate_", "Checks"), ("publish_", "Publishing")):
        if name.startswith(prefix):
            return label
    return "Caches" if "cachix" in name else "Automation"


def platform(path, name):
    value = path.lower()
    if name.startswith("cross-compile-test"):
        return "arm"
    for token, result in (("tdx", "tdx"), ("riscv", "riscv"), ("loongarch", "loong"), ("aarch64", "arm")):
        if token in value:
            return result
    if any(token in value for token in ("x86", "vmx", "vsock", "nixos", "xfstests", "iso_image")):
        return "x86"
    return None


def test_suite(path, name):
    """Map known runtime/build jobs; selector and cache jobs are not test passes."""
    filename = path.rsplit("/", 1)[-1]
    if filename == "test_nixos_full.yml":
        return "nixos/" + name[5:] if name.startswith("Test ") else None
    if filename == "test_nixos_minimal.yml":
        return "nixos/hello" if name == "minimal-nixos-test" else None
    if filename == "test_loongarch.yml":
        return "lint" if "lint" in name else "compile" if "compile" in name else None
    if filename == "test_aarch64.yml":
        return next((suite for prefix, suite in (("compile (", "compile"), ("lint (", "lint"),
                     ("boot (", "boot"), ("conformance (", "conformance/ltp")) if name.startswith(prefix)), None)
    if filename == "test_iso_image.yml":
        return "boot/iso" if name == "iso-test" else None
    if filename == "test_vmx.yml":
        return "kernel/vmx" if name == "ktest-vmx" else None
    if name.startswith("basic-test ("):
        variant = name.split("(", 1)[1].split(")", 1)[0]
        return {"ktest": "kernel/ktest", "usermode_test": "usermode", "lint": "lint", "compile": "compile"}.get(variant)
    if name.startswith("integration-test ("):
        return "conformance/ltp" if "conformance" in name else "boot" if "boot" in name else None
    if name.startswith("conformance-test ("):
        return "conformance/" + name.split("(", 1)[1].split(",", 1)[0].strip()
    for prefix, suite in (("boot-test", "boot"), ("cross-compile-test", "boot"),
                          ("regression-test", "regression"), ("xfstests", "fs/xfstests"),
                          ("pjdfstest", "fs/pjdfstest"), ("osdk-test", "osdk")):
        if name.startswith(prefix):
            return suite
    # Other testing workflows remain visible in Overview; unknown jobs are not
    # guessed into a suite. Explicit adapters can extend this map later.
    return None


def run_identity(run):
    return {key: run.get(key) for key in ("id", "name", "head_sha", "head_branch", "event", "status", "conclusion",
            "run_attempt", "created_at", "run_started_at", "updated_at", "html_url", "path")}


def refresh(manifest, repository, fetch, save, clock):
    """Archive bounded backfill plus previously retained runs, using read-only APIs."""
    revision = fetch(f"repos/{repository}/commits/main")["sha"]
    files = fetch(f"repos/{repository}/contents/.github/workflows?ref={revision}")
    defined = {file["path"] for file in files if file["name"].endswith((".yml", ".yaml"))}
    registered, page = [], 1
    while True:
        payload = fetch(f"repos/{repository}/actions/workflows?per_page=100&page={page}")
        registered.extend(payload["workflows"])
        if len(registered) >= payload["total_count"]:
            break
        page += 1
    # Deleted paths can remain active in the registry. Only current definitions
    # and GitHub-managed workflows belong to the enabled overview.
    workflows = [w for w in registered if w["state"] == "active"
                 and (w["path"] in defined or w["path"].startswith("dynamic/"))]
    collected = clock()
    sources = []

    def collect_history(workflow):
        endpoint = f"repos/{repository}/actions/workflows/{workflow['id']}/runs?branch=main&status=completed&per_page=100"
        try:
            payload = fetch(endpoint)
            runs = sorted((run for run in payload["workflow_runs"] if eligible(run, repository)),
                          key=lambda run: (run["created_at"], run["id"]), reverse=True)
            selected = runs[:HISTORY_LIMIT] if category(workflow["path"]) == "Tests" else runs[:1]
            record = {"workflow": workflow, "runs": selected, "error": None,
                      "queried_at": clock(), "query_total": payload["total_count"],
                      "backfill_limit": HISTORY_LIMIT if category(workflow["path"]) == "Tests" else 1}
        except subprocess.CalledProcessError:
            record = {"workflow": workflow, "runs": [], "error": "GitHub run history unavailable", "queried_at": clock()}
        return record, save(f"main-history-{workflow['id']}.json", record,
                            f"https://api.github.com/{endpoint}", "main_history", revision)

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        histories = list(pool.map(collect_history, workflows))
    sources.extend(source for _, source in histories)
    # Retain archived run records during refresh. Backfill bounds describe the
    # initial search; incremental collection must not erase older configurations.
    known = {source["id"]: source for source in manifest["sources"]}
    run_records = {f"run-{run['id']}.json": run for record, _ in histories for run in record["runs"]}

    def collect_run(item):
        name, run = item
        entries = [save(name, run, run["html_url"], "ci_run", run["head_sha"])]
        for attempt in range(1, run["run_attempt"] + 1):
            source_id = f"jobs-{run['id']}-{attempt}.json"
            if source_id in known and attempt < run["run_attempt"]:
                continue
            jobs, page = [], 1
            while True:
                endpoint = f"repos/{repository}/actions/runs/{run['id']}/attempts/{attempt}/jobs?per_page=100&page={page}"
                payload = fetch(endpoint)
                jobs.extend(payload["jobs"])
                if len(jobs) >= payload["total_count"]:
                    break
                page += 1
            entries.append(save(source_id, {"total_count": len(jobs), "jobs": jobs},
                                f"https://api.github.com/{endpoint}", "ci_jobs", run["head_sha"]))
        return entries

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for entries in pool.map(collect_run, run_records.items()):
            sources.extend(entries)
    catalog = {"repository": repository, "branch": "main", "head_sha": revision, "collected_at": collected,
               "workflows": workflows, "registered_count": len(registered), "definition_paths": sorted(defined),
               "events": sorted(EVENTS), "history_limit": HISTORY_LIMIT}
    sources.append(save("main-catalog.json", catalog,
                        f"https://github.com/{repository}/tree/{revision}/.github/workflows", "main_catalog", revision))
    known.update({source["id"]: source for source in sources})
    manifest["sources"] = sorted(known.values(), key=lambda source: source["id"])
    manifest["main_collected_at"] = collected


def execution_order(record):
    return (record["run"]["created_at"], record["run"]["id"], record["execution_attempt"], record["started_at"] or "", record["origin_job_id"])


def aggregate(records):
    """Latest execution and strictly earlier successful execution per observed key."""
    groups = {}
    for record in records:
        # A skipped job did not execute. A cancellation without any executed
        # steps also must not erase the most recent actual execution.
        executed_steps = any(step.get("started_at") and step.get("conclusion") != "skipped"
                             for step in record["steps"])
        if record["conclusion"] == "skipped" or (record["conclusion"] == "cancelled" and not executed_steps):
            continue
        if record["status"] != "completed":
            continue
        groups.setdefault(record["config_key"], {})[record["origin_job_id"]] = record
    results = []
    for key, executions in groups.items():
        ordered = sorted(executions.values(), key=execution_order, reverse=True)
        latest = ordered[0]
        success = next((record for record in ordered[1:] if record["conclusion"] == "success"), None)
        results.append({"key": key, "suite": latest["suite"], "platform": latest["platform"],
                        "latest": latest["id"], "previous_success": success["id"] if success else None})
    return sorted(results, key=lambda result: (result["suite"], result["platform"] or "", result["key"]))


def build(archive, parse_job, execution_origin):
    if "main-catalog.json" not in archive.entries:
        return None
    catalog = archive.json("main-catalog.json")
    workflows, records = [], []
    retained_runs = [archive.json(source_id) for source_id in archive.entries if re.fullmatch(r"run-\d+\.json", source_id)]
    for workflow in catalog["workflows"]:
        history = archive.json(f"main-history-{workflow['id']}.json")
        path = workflow["path"]
        # Include retained history, not just this fetch's limited backfill.
        runs = [run for run in retained_runs if run.get("workflow_id") == workflow["id"] and eligible(run, catalog["repository"])]
        runs.sort(key=lambda run: (run["created_at"], run["id"]), reverse=True)
        latest_jobs = archive.json(f"jobs-{runs[0]['id']}-{runs[0]['run_attempt']}.json")["jobs"] if runs else []
        platforms = sorted({platform(path, job["name"]) for job in latest_jobs} - {None}) if category(path) in ("Tests", "Benchmarks") else []
        workflows.append({**workflow, "id": str(workflow["id"]), "category": category(path),
                          "latest": run_identity(runs[0]) if runs else None, "error": history.get("error"),
                          "history_runs": len(runs), "queried_at": history["queried_at"],
                          "platform_stats": [{"platform": target, "total": len(jobs := [job for job in latest_jobs if platform(path, job["name"]) == target]),
                              "success": sum(job["conclusion"] == "success" for job in jobs),
                              "failure": sum(job["conclusion"] == "failure" for job in jobs),
                              "other": sum(job["conclusion"] not in ("success", "failure") for job in jobs)} for target in platforms]})
        if category(path) != "Tests":
            continue
        for run in runs:
            attempts = [archive.json(f"jobs-{run['id']}-{attempt}.json") for attempt in range(1, run["run_attempt"] + 1)]
            seen = set()
            # Keep successful attempts even when a later rerun fails. Cloned
            # successes are deduplicated by original execution ID.
            for index, jobs in enumerate(attempts):
                for job in jobs["jobs"]:
                    suite = test_suite(path, job["name"])
                    if not suite:
                        continue
                    origin = execution_origin(job, attempts[:index])
                    if origin["id"] in seen:
                        continue
                    seen.add(origin["id"])
                    observation = parse_job(job, origin, archive, suite=suite)
                    observation.update({"suite": suite, "platform": platform(path, job["name"]),
                        "workflow_id": str(workflow["id"]), "workflow_name": workflow["name"], "workflow_path": path,
                        "config_key": json.dumps([path, job["name"], platform(path, job["name"])], separators=(",", ":")),
                        "run": run_identity(run)})
                    records.append(observation)
    results = aggregate(records)
    referenced = {record_id for result in results for record_id in (result["latest"], result["previous_success"]) if record_id}
    return {**catalog, "workflows": workflows, "records": [record for record in records if record["id"] in referenced], "results": results}
