#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Import pinned public observations; never manufacture canonical CI reports.

Run with --refresh to fetch public sources using an authenticated gh installation.
Without --refresh, rebuilding is offline and uses the hashed source archive.
"""

import argparse
import base64
import concurrent.futures
import datetime as dt
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

import main_results

QA = Path(__file__).resolve().parents[1]
SOURCES = QA / "data/sources"
REPO = "asterinas/asterinas"
BOOK = "book/src/kernel/linux-compatibility"
METRICS = [
    ("lmbench", "process_fork_lat", "Fork + exit", "Process", "lower"),
    ("schbench", "smp8_p99_wakeup_latency", "P99 wakeup latency · SMP 8", "Scheduler", "lower"),
    ("fio", "ext2_seq_read_bw_direct", "Ext2 sequential read · direct I/O", "Storage", "higher"),
    ("iperf3", "tcp_virtio_bw", "TCP receive bandwidth", "Network", "higher"),
    ("redis", "get_100k_conc20_rps", "Redis GET · 20 clients", "Application", "higher"),
    ("boot", "boot_lat", "Boot · minimal initramfs", "Boot", "lower"),
]
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def gh(endpoint):
    return subprocess.check_output(["gh", "api", endpoint])


def gh_json(endpoint):
    return json.loads(gh(endpoint))


def all_jobs(run_id, attempt):
    jobs = []
    page = 1
    while True:
        result = gh_json(f"repos/{REPO}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100&page={page}")
        jobs.extend(result["jobs"])
        if len(jobs) >= result["total_count"]:
            return {"total_count": result["total_count"], "jobs": jobs}
        page += 1


def archive(name, raw, url, kind, revision=None):
    if not isinstance(raw, bytes):
        raw = json.dumps(raw, ensure_ascii=False, indent=2).encode() + b"\n"
    path = name + ".gz"
    (SOURCES / path).write_bytes(gzip.compress(raw, mtime=0))
    return {"id": name, "kind": kind, "url": url, "revision": revision,
            "observed_at": now(), "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw), "cache": path}


def execution_origin(job, previous_attempts):
    # GitHub can clone a successful job into a rerun's job list, changing both
    # ID and run_attempt. Match execution timestamps, not the cloned identity.
    for attempt in previous_attempts:
        for old in attempt["jobs"]:
            if all(old.get(key) == job.get(key) for key in
                   ("name", "started_at", "completed_at", "conclusion")):
                return old
    return job


def sample_previous(job):
    name = job["name"]
    return name.startswith(("basic-test (ktest)", "basic-test (usermode_test)",
        "regression-test (multiboot2", "boot-test (multiboot2-smp4,",
        "conformance-test (ltp, multiboot", "conformance-test (gvisor, multiboot",
        "conformance-test (kselftest, multiboot", "xfstests (ext2)",
        "pjdfstest (ext2)", "osdk-test (asterinas/kernel"))


def refresh():
    SOURCES.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((SOURCES / "manifest.json").read_text()) if (SOURCES / "manifest.json").exists() else {"format": "qa-source-archive-v1", "sources": []}
    retained = {entry["id"]: entry for entry in manifest["sources"]}
    manifest.update({"fetched_at": now(), "sources": []})
    entries = manifest["sources"]
    runs = gh_json(f"repos/{REPO}/actions/workflows/test_x86.yml/runs?branch=main&event=push&per_page=2")["workflow_runs"]
    manifest["run_ids"] = [run["id"] for run in runs]
    log_jobs = {}
    for index, run in enumerate(runs):
        run = gh_json(f"repos/{REPO}/actions/runs/{run['id']}")
        run_id = run["id"]
        entries.append(archive(f"run-{run_id}.json", run, run["html_url"], "ci_run", run["head_sha"]))
        attempts = []
        for attempt in range(1, run["run_attempt"] + 1):
            jobs = all_jobs(run_id, attempt)
            entries.append(archive(f"jobs-{run_id}-{attempt}.json", jobs,
                f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/attempts/{attempt}/jobs", "ci_jobs", run["head_sha"]))
            attempts.append(jobs)
        for job in attempts[-1]["jobs"]:
            if index == 0 or sample_previous(job):
                origin = execution_origin(job, attempts[:-1])
                log_jobs[origin["id"]] = origin
        workflow_path = run["path"].split("@", 1)[0]
        workflow = gh_json(f"repos/{REPO}/contents/{workflow_path}?ref={run['head_sha']}")
        entries.append(archive(f"workflow-{run_id}.yml", base64.b64decode(workflow["content"]),
            f"https://github.com/{REPO}/blob/{run['head_sha']}/{workflow_path}", "workflow", run["head_sha"]))

    def fetch_log(job):
        endpoint = f"repos/{REPO}/actions/jobs/{job['id']}/logs"
        try:
            return archive(f"job-{job['id']}.log", gh(endpoint), job["html_url"], "ci_log", job["head_sha"])
        except subprocess.CalledProcessError:
            return {"id": f"job-{job['id']}.log", "kind": "ci_log", "url": job["html_url"],
                    "observed_at": now(), "error": "Log unavailable from GitHub", "cache": None}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        entries.extend(pool.map(fetch_log, log_jobs.values()))

    retained.update({entry["id"]: entry for entry in entries})
    manifest["sources"] = sorted(retained.values(), key=lambda entry: entry["id"])
    refresh_book(manifest)
    refresh_benchmark(manifest)
    main_results.refresh(manifest, REPO, gh_json, archive, now)
    refresh_nixos_logs(manifest)
    (SOURCES / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def refresh_book(manifest):
    """Refresh declarations independently, pinned to the remote main revision."""
    revision = gh_json(f"repos/{REPO}/commits/main")["sha"]
    tree = gh_json(f"repos/{REPO}/git/trees/{revision}?recursive=1")
    assert not tree["truncated"], "source tree is truncated"
    files = [item for item in tree["tree"] if item["path"].startswith(BOOK + "/")
             and item["path"].endswith((".md", ".scml")) and item["type"] == "blob"]

    def fetch_document(item):
        blob = gh_json(f"repos/{REPO}/git/blobs/{item['sha']}")
        return item["path"], base64.b64decode(blob["content"]).decode()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        documents = dict(pool.map(fetch_document, files))
    parse_api(documents, revision)  # Validate before replacing a reliable source.
    source = archive("book.json", documents, f"https://github.com/{REPO}/tree/{revision}/{BOOK}", "book", revision)
    entries = {entry["id"]: entry for entry in manifest["sources"]}
    entries[source["id"]] = source
    manifest["sources"] = sorted(entries.values(), key=lambda entry: entry["id"])
    manifest["book_sha"] = revision


def refresh_benchmark(manifest):
    """Import selected metric sources from one pinned benchmark revision."""
    tree = gh_json("repos/asterinas/benchmark/git/trees/gh-pages?recursive=1")
    assert not tree["truncated"], "benchmark tree is truncated"

    def fetch_metric(metric):
        suite = metric[0]
        path = f"x86-64/{suite}/data.js"
        blob = next(item for item in tree["tree"] if item["path"] == path)
        payload = gh_json(f"repos/asterinas/benchmark/git/blobs/{blob['sha']}")
        return archive(f"benchmark-{suite}.js", base64.b64decode(payload["content"]),
                       f"https://github.com/asterinas/benchmark/blob/{tree['sha']}/{path}", "benchmark", tree["sha"])

    entries = {entry["id"]: entry for entry in manifest["sources"]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        entries.update({entry["id"]: entry for entry in pool.map(fetch_metric, METRICS)})
    manifest["sources"] = sorted(entries.values(), key=lambda entry: entry["id"])
    manifest["benchmark_sha"] = tree["sha"]
    manifest["benchmark_collected_at"] = now()


def refresh_nixos_logs(manifest):
    """Archive native counts for each observed NixOS suite's two displayed executions."""
    sources = {entry["id"]: entry for entry in manifest["sources"]}
    observations = main_results.build(Archive(manifest), parse_job, execution_origin)
    jobs = {record["origin_job_id"]: record for record in observations["records"]
            if record["suite"].startswith("nixos/")}

    def fetch_log(record):
        name = f"job-{record['origin_job_id']}.log"
        if sources.get(name, {}).get("cache"):
            return sources[name]
        try:
            return archive(name, gh(f"repos/{REPO}/actions/jobs/{record['origin_job_id']}/logs"),
                           record["url"], "ci_log", record["run"]["head_sha"])
        except subprocess.CalledProcessError:
            return {"id": name, "kind": "ci_log", "url": record["url"], "observed_at": now(),
                    "error": "Log unavailable from GitHub", "cache": None}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        sources.update({entry["id"]: entry for entry in pool.map(fetch_log, jobs.values())})
    manifest["sources"] = sorted(sources.values(), key=lambda entry: entry["id"])


class Archive:
    def __init__(self, manifest=None):
        self.manifest = manifest if manifest is not None else json.loads((SOURCES / "manifest.json").read_text())
        self.entries = {entry["id"]: entry for entry in self.manifest["sources"]}

    def text(self, name):
        entry = self.entries.get(name)
        if not entry or not entry.get("cache"):
            return None
        raw = gzip.decompress((SOURCES / entry["cache"]).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"], f"source hash mismatch: {name}"
        return raw.decode()

    def json(self, name):
        return json.loads(self.text(name))


def clean_log(text):
    return [re.sub(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ?", "", ANSI.sub("", line))
            for line in text.splitlines()]


def native_summary(lines, suite):
    text = "\n".join(lines)
    if suite.startswith("nixos/"):
        # The host framework emits these counts after running its case loop.
        # Nested application output and individual case lines are not totals.
        matches = re.findall(r"^=== Test Summary ===\s*\nPassed: (\d+)\s*\nFailed: (\d+)\s*$", text, re.M)
        if matches:
            passed, failed = matches[-1]
            return {"kind": "NixOS host test summary", "counts": {"passed": int(passed), "failed": int(failed)},
                    "scope": "Final emitted host-framework summary for this NixOS suite. Counts are top-level test cases, not nested application assertions or a code-coverage denominator."}
    if suite in ("kernel/ktest", "usermode", "osdk"):
        matches = re.findall(r"test result: (?:ok|FAILED)\. (\d+) passed; (\d+) failed;(?: (\d+) ignored;)?", text)
        if matches:
            totals = [sum(int(row[index] or 0) for row in matches) for index in range(3)]
            return {"kind": "Rust harness summaries", "counts": dict(zip(("passed", "failed", "ignored"), totals)),
                    "scope": f"Sum of {len(matches)} emitted harness summaries in this job; not unique test or code coverage."}
    if suite == "conformance/ltp":
        summary = text.rsplit("TEST SUMMARY", 1)[-1]
        counts = {key.lower(): int(value) for key, value in re.findall(r"^\s*(Runs|Passed|Failed|Broken|Skipped|Warnings):\s*(\d+)\s*$", summary, re.M)}
        if "passed" in counts:
            return {"kind": "LTP native summary", "counts": counts,
                    "scope": "Selected syscalls suite and blocklists. Runs and subtest result counts use different units."}
    if suite == "conformance/gvisor":
        counts = {key: sum(map(int, re.findall(pattern, text))) for key, pattern in {
            "passed": r"\[\s*PASSED\s*\]\s+(\d+) tests?\.",
            "skipped": r"\[\s*SKIPPED\s*\]\s+(\d+) tests?, listed below:",
            "ran": r"\[==========\] (\d+) tests? from .* ran\."}.items()}
        if counts["ran"]:
            return {"kind": "GoogleTest binary summaries", "counts": counts,
                    "scope": "Sum of emitted binary summaries for this selected gVisor configuration; excluded tests remain outside this count."}
    if suite == "conformance/kselftest" and "All kselftest tests passed." in text:
        return {"kind": "kselftest driver results", "counts": {
            "passed binaries": len(re.findall(r"\[\s*PASSED\s*\]:", text)),
            "skipped binaries": len(re.findall(r"\[\s*SKIPPED\s*\]:", text))},
            "scope": "Top-level driver result lines, not nested TAP assertions or the complete upstream suite."}
    if suite == "fs/xfstests":
        match = re.search(r"^Passed all (\d+) tests\s*$", text, re.M)
        if match:
            return {"kind": "xfstests native summary", "counts": {"passed": int(match[1])},
                    "scope": "Selected filesystem and runlist only; not the full upstream xfstests inventory."}
    if suite == "fs/pjdfstest":
        match = re.search(r"Files=(\d+), Tests=(\d+),", text)
        if match:
            return {"kind": "Perl TAP harness", "counts": {"files": int(match[1]), "assertions": int(match[2])},
                    "scope": "Native Result: PASS includes TAP skip/TODO semantics. The assertion count is not a verified-pass denominator; the log also reports a tee warning."}
    return None


def suite_for(name):
    if name.startswith("basic-test"):
        variant = name.split("(", 1)[1].split(")", 1)[0]
        return {"ktest": "kernel/ktest", "usermode_test": "usermode"}.get(variant, variant)
    if name.startswith("conformance-test"):
        return "conformance/" + name.split("(", 1)[1].split(",", 1)[0]
    for prefix, suite in (("boot-test", "boot"), ("cross-compile-test", "boot"),
                          ("regression-test", "regression"), ("xfstests", "fs/xfstests"),
                          ("pjdfstest", "fs/pjdfstest"), ("osdk-test", "osdk")):
        if name.startswith(prefix):
            return suite
    return "other"


def parse_job(job, origin, archive, suite=None):
    text = archive.text(f"job-{origin['id']}.log")
    lines = clean_log(text) if text else []
    suite = suite if suite is not None else suite_for(job["name"])
    command = next((line.removeprefix("Executing: ") for line in lines if line.startswith("Executing: ")), None)
    checkout_shas = [lines[index + 1] for index, line in enumerate(lines[:-1])
                     if "git log -1 --format=%H" in line and re.fullmatch(r"[a-f0-9]{40}", lines[index + 1])]
    errors = [line for line in lines if re.match(r"error(?:\[E\d+\])?:|\[Error\]", line)][:4]
    summary = native_summary(lines, suite)
    evidence_pattern = r"test result:|Test Summary|Passed:|Failed:|Broken:|Skipped:|Runs:|Files=|Result:|Passed all \d+ tests|All .*tests passed|^error(?:\[|:)|\[Error\]"
    excerpt = [line for line in lines if re.search(evidence_pattern, line)][-12:]
    if summary is None and not errors:
        excerpt = [line for line in lines if "[  PASSED" in line][-8:] or excerpt
    return {"id": str(job["id"]), "origin_job_id": str(origin["id"]), "name": job["name"],
            "suite": suite, "platform": "arm" if job["name"].startswith("cross-compile-test") else "x86",
            "conclusion": job["conclusion"], "status": job["status"],
            "listed_attempt": job["run_attempt"], "execution_attempt": origin["run_attempt"],
            "inherited": job["id"] != origin["id"], "started_at": origin["started_at"],
            "completed_at": origin["completed_at"], "url": origin["html_url"],
            "listed_url": job["html_url"], "command": command,
            "checkout_sha": checkout_shas[-1] if checkout_shas else None,
            "errors": errors, "native_summary": summary, "excerpt": excerpt,
            "log_source_id": f"job-{origin['id']}.log" if text else None,
            "steps": [{key: step.get(key) for key in ("name", "number", "conclusion", "started_at", "completed_at")}
                      for step in origin["steps"]]}


def parse_api(documents, source_sha):
    root_path = f"{BOOK}/README.md"
    syscall_categories = {}
    for path, text in documents.items():
        if path.endswith(".scml"):
            for name in re.findall(r"\b([a-z][a-z0-9_]+)\s*\(", text):
                syscall_categories.setdefault(name, path.split("/")[-2])
    result = []
    for line in documents[root_path].splitlines():
        columns = [cell.strip() for cell in line.strip("|").split("|")]
        if len(columns) != 4 or not columns[0].isdigit():
            continue
        number, name, support, coverage = columns
        target = re.search(r"\]\(([^)]+)\)", coverage)
        details, scml = "", []
        path = root_path
        category = syscall_categories.get(name, "unclassified")
        if target:
            target_path, anchor = target[1].split("#", 1)
            path = f"{BOOK}/{target_path.rstrip('/')}/README.md"
            category = target_path.strip("/").split("/")[-1]
            text = documents[path]
            sections = re.split(r"(?m)^(?=#{2,4} )", text)
            def heading_anchor(section):
                heading = section.splitlines()[0].lstrip("# ").replace("`", "")
                return re.sub(r"[^\w -]", "", heading.lower()).replace(" ", "-")
            section = next((s for s in sections if heading_anchor(s) == anchor), "")
            assert section, f"missing Book section: {name} #{anchor}"
            details = re.sub(r"```[^\n]*\n?|\{\{#include [^}]+\}\}", "", section).strip()
            for include in re.findall(r"\{\{#include ([^}]+)\}\}", section):
                include_path = str(Path(path).parent / include.split(":", 1)[0])
                scml.append({"path": include_path, "text": documents[include_path]})
        flags = "partial" if target else "full" if "💯" in coverage else "not_applicable"
        status = "unsupported" if "❌" in support else "partial" if flags == "partial" else "supported"
        result.append({"id": f"x86_64/{name}", "name": name, "number": int(number), "arch": "x86_64",
            "declared_supported": "✅" in support, "status": status, "flag_coverage": flags,
            "category": category.replace("-", " ").title(), "details": details, "scml": scml,
            "url": f"https://github.com/{REPO}/blob/{source_sha}/{path}" + (f"#{target[1].split('#')[1]}" if target else ""),
            "source_path": path})
    assert len(result) > 300 and len({entry['number'] for entry in result}) == len(result)
    return {"source_sha": source_sha, "entries": result,
            "url": f"https://github.com/{REPO}/blob/{source_sha}/{root_path}"}


def parse_benchmarks(archive):
    result = []
    for suite, key, name, category, direction in METRICS:
        # Only parse a known assignment. Remote JavaScript is never executed.
        raw = archive.text(f"benchmark-{suite}.js")
        match = re.fullmatch(r"\s*window\.BENCHMARK_DATA\s*=\s*(\{.*\})\s*;?\s*", raw, re.S)
        assert match, f"unexpected benchmark JavaScript: {suite}"
        data = json.loads(match[1])
        points = []
        for item in data["entries"][key]:
            measurements = {}
            for system, extra in (("asterinas", "aster_result"), ("linux", "linux_result")):
                bench = next((bench for bench in item["benches"] if bench.get("extra") == extra), None)
                value = float(bench["value"]) if bench else None
                assert value is None or math.isfinite(value)
                measurements[system] = {"value": value, "raw_value": bench["value"] if bench else None,
                                        "unit": bench["unit"] if bench else None}
            assert item["tool"] == ("customSmallerIsBetter" if direction == "lower" else "customBiggerIsBetter")
            points.append({"at": dt.datetime.fromtimestamp(item["date"] / 1000, dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "published_ref": item["commit"]["id"], "commit_url": item["commit"]["url"],
                "title": item["title"], "description": item["description"], "display": item.get("display"),
                **measurements, "environment_id": None, "tested_sha": None, "run_id": None})
        points.sort(key=lambda point: point["at"])
        entry = archive.entries[f"benchmark-{suite}.js"]
        result.append({"id": key, "suite": suite, "name": name, "category": category,
                       "direction": direction, "platform": "x86", "points": points,
                       "source_id": entry["id"], "url": entry["url"],
                       "published_at": dt.datetime.fromtimestamp(data["lastUpdate"] / 1000, dt.timezone.utc).isoformat().replace("+00:00", "Z")})
    return result


def build():
    archive = Archive()
    snapshots = []
    for run_id in archive.manifest["run_ids"]:
        run = archive.json(f"run-{run_id}.json")
        attempt = run["run_attempt"]
        attempts = [archive.json(f"jobs-{run_id}-{n}.json") for n in range(1, attempt)]
        jobs = archive.json(f"jobs-{run_id}-{attempt}.json")
        snapshots.append({"main_sha": run["head_sha"], "run_id": run_id, "attempt": attempt,
            "created_at": run["created_at"], "updated_at": run["updated_at"], "url": run["html_url"],
            "conclusion": run["conclusion"], "workflow": run["name"], "job_count": jobs["total_count"],
            "jobs": [parse_job(job, execution_origin(job, attempts), archive) for job in jobs["jobs"]]})
    data = {"format": "qa-observations-v1", "mode": "real", "fetched_at": archive.manifest["fetched_at"],
            "snapshots": snapshots, "api": parse_api(archive.json("book.json"), archive.manifest["book_sha"]),
            "metrics": parse_benchmarks(archive), "sources": archive.manifest["sources"],
            "main_results": main_results.build(archive, parse_job, execution_origin),
            "benchmark_sha": archive.manifest["benchmark_sha"],
            "presentation": {"platforms": [
                {"id": "x86", "arch": "x86_64", "label": "x86-64"},
                {"id": "tdx", "arch": "x86_64", "label": "Intel TDX"},
                {"id": "arm", "arch": "aarch64", "label": "AArch64"},
                {"id": "riscv", "arch": "riscv64", "label": "RISC-V 64"},
                {"id": "loong", "arch": "loongarch64", "label": "LoongArch 64"}]}}
    (QA / "data/real.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    ci = data["main_results"]
    print(f"Imported {len(ci['workflows'])} enabled workflows, {len(ci['results'])} test configurations, "
          f"{len(data['api']['entries'])} syscall declarations, "
          f"{sum(len(m['points']) for m in data['metrics'])} historical benchmark pairs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="read public GitHub sources; requires gh")
    parser.add_argument("--refresh-main", action="store_true", help="collect enabled main workflows and per-configuration execution history")
    parser.add_argument("--refresh-book", action="store_true", help="refresh API declarations from remote main independently")
    parser.add_argument("--refresh-benchmark", action="store_true", help="refresh selected metrics from benchmark gh-pages independently")
    parser.add_argument("--refresh-nixos-logs", action="store_true", help="import native logs for latest and previous successful NixOS executions")
    args = parser.parse_args()
    if args.refresh:
        refresh()
    elif args.refresh_main or args.refresh_book or args.refresh_benchmark or args.refresh_nixos_logs:
        manifest = json.loads((SOURCES / "manifest.json").read_text())
        if args.refresh_main:
            main_results.refresh(manifest, REPO, gh_json, archive, now)
        if args.refresh_book:
            refresh_book(manifest)
        if args.refresh_benchmark:
            refresh_benchmark(manifest)
        if args.refresh_main or args.refresh_nixos_logs:
            refresh_nixos_logs(manifest)
        (SOURCES / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    build()
