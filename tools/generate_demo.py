#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0

"""Generate fictional v1.0 QA records and separate presentation metadata."""

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc).replace(second=0, microsecond=0)
SHAS = [hashlib.sha1(f"qa-fictional-snapshot-{i}".encode()).hexdigest() for i in range(2)]
PRODUCER = {"name": "qa-demo-fixture", "version": "1.0"}
POLICY = {"id": "demo-policy-not-for-merge", "status": "provisional"}
PLATFORMS = [
    {"id": "x86", "label": "x86-64", "arch": "x86_64", "platform": "qemu", "note": "QEMU / KVM"},
    {"id": "tdx", "label": "Intel TDX", "arch": "x86_64", "platform": "tdx", "note": "x86-64 · confidential VM"},
    {"id": "arm", "label": "ARM64", "arch": "aarch64", "platform": "qemu", "note": "Boot and build checks"},
    {"id": "riscv", "label": "RISC-V 64", "arch": "riscv64", "platform": "qemu", "note": "QEMU · SMP 1 / 4"},
    {"id": "loong", "label": "LoongArch 64", "arch": "loongarch64", "platform": "qemu", "note": "Build checks only"},
]
SUITES = [
    {"id": "boot", "name": "Boot", "description": "Kernel boot and success marker", "kind": "runtime"},
    {"id": "regression", "name": "Regression", "description": "User-space regression tests", "kind": "runtime"},
    {"id": "kernel/ktest", "name": "Kernel tests", "description": "Kernel-mode unit tests", "kind": "runtime"},
    {"id": "conformance/ltp", "name": "LTP", "description": "Linux Test Project", "kind": "runtime"},
    {"id": "conformance/gvisor", "name": "gVisor", "description": "System call behavior tests", "kind": "runtime"},
    {"id": "conformance/kselftest", "name": "kselftest", "description": "Linux kernel selftests", "kind": "runtime"},
    {"id": "fs/xfstests", "name": "xfstests", "description": "Filesystem · short / full", "kind": "runtime"},
    {"id": "fs/pjdfstest", "name": "pjdfstest", "description": "POSIX filesystem semantics", "kind": "runtime"},
    {"id": "nixos", "name": "NixOS", "description": "Applications · minimal / full", "kind": "runtime"},
    {"id": "build", "name": "Compile", "description": "Standalone build checks", "kind": "build"},
]
METRICS = [
    {"id": "process/fork-exit", "name": "fork + exit", "category": "Processes", "description": "Process creation and exit latency", "unit": "us", "direction": "lower", "values": [42.8, 58.2], "reason": "Represents basic process operations with a fixed single-process workload."},
    {"id": "scheduler/schbench-p99", "name": "schbench p99", "category": "Scheduling", "description": "SMP8 wakeup latency", "unit": "us", "direction": "lower", "values": [26.4, 31.8], "reason": "Tracks tail latency with a fixed SMP8 configuration and workload."},
    {"id": "storage/ext2-direct-read", "name": "Ext2 sequential read", "category": "Storage", "description": "Sequential direct I/O read", "unit": "MB/s", "direction": "higher", "values": [1940, 1720], "reason": "Represents sequential reads using Ext2 and direct I/O."},
    {"id": "network/iperf3-tcp", "name": "iperf3 TCP", "category": "Networking", "description": "virtio TCP throughput", "unit": "Gbit/s", "direction": "higher", "values": [8.62, 9.14], "reason": "Represents TCP throughput with fixed virtio devices and host/guest networking."},
    {"id": "application/redis-get", "name": "Redis GET", "category": "Applications", "description": "Single-instance read throughput", "unit": "req/s", "direction": "higher", "values": [118400, 105200], "reason": "Represents key-value reads with a fixed request count and concurrency."},
    {"id": "boot/latency", "name": "Boot latency", "category": "Boot", "description": "Boot to success marker", "unit": "ms", "direction": "lower", "values": [185, None], "reason": "Tracks a fixed boot sequence; retained even when the Linux measurement is missing."},
]


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def record(kind, identity):
    return {"schema_version": "1.0", "kind": kind, "record_id": identity, "example": True, "producer": PRODUCER}


def source(sha, path):
    return {"sha": sha, "path": path, "locator": None, "url": f"https://example.invalid/source/{sha}/{path}"}


def platform_id(config):
    return next(p["id"] for p in PLATFORMS if p["arch"] == config["arch"] and p["platform"] == config["platform"])


def config_for(platform, index=0, suite="boot"):
    parameters = {"RELEASE": "1", "RELEASE_LTO": "0", "ENABLE_KVM": "1" if platform["id"] == "x86" else "0", "SCHEME": "riscv" if platform["id"] == "riscv" else "default", "FEATURES": "default", "INITRAMFS": "test", "OVMF": "off"}
    if suite == "kernel/ktest":
        parameters.update(NETDEV="tap", CONSOLE="ttyS0")
    config = {"arch": platform["arch"], "platform": platform["platform"], "profile": "release", "smp": 4 if index else 1, "mem_mib": 8192, "filesystem": "ext2" if suite.startswith("fs/") else "none", "boot_method": "qemu", "boot_protocol": "multiboot2" if platform["arch"] == "x86_64" else "direct", "parameters": parameters, "unresolved_fields": []}
    if suite == "nixos":
        config.update(profile="debug", smp=1, filesystem="ext2", boot_protocol="linux-efi-handover64")
        parameters.update(RELEASE="0", INITRAMFS="none", ROOTFS="nixos", SUITE_SET="full" if index else "minimal")
    if suite == "boot" and index == 2:
        config["boot_protocol"] = "linux-efi-handover64"
    if suite == "fs/xfstests":
        parameters["TEST_SELECTION"] = "full" if index else "short"
    return config


def environment():
    return {"container_ref": "example/kernel-dev:demo", "container_digest": digest("demo-container"), "host_arch": "x86_64", "runner_class": "fictional-dedicated-runner", "cpu_model": "Intel Xeon Gold 6430 (example)", "microcode": "0x2b000643 (example)", "host_kernel": "Linux 6.12 (example)", "qemu_version": "9.2.0 (example)", "rust_toolchain": "nightly-2026-10-12 (example)", "nix_version": "2.28 (example)", "flake_lock_digest": digest("demo-lock"), "linux_kernel_version": "6.12 (example)", "linux_kernel_digest": digest("demo-linux"), "details": {"host_os": "Ubuntu 24.04 (example)", "vcpus": "8", "memory": "8192 MiB", "workload": "Fixed demo workload", "devices": "virtio-net / virtio-blk", "firmware": "demo-firmware-v1", "method": "demo-paired-v1"}, "unresolved_fields": []}


def main():
    result = {"catalogs": [], "plans": [], "reports": [], "api_declarations": [], "snapshots": [], "presentation": {"example": True, "platforms": PLATFORMS, "suites": SUITES, "metrics": METRICS, "groups": {}, "history": [], "cases": {}}}
    layout = {
        "x86": [["passed"] * 3, ["passed"] * 2, ["passed", "running"], ["passed", "failed"], ["passed"] * 2, ["passed"], ["passed", "missing_report"], ["passed"], ["passed", "not_selected"], ["passed"] * 2],
        "tdx": [["passed"], ["cancelled"], [], ["unknown"], [], [], [], [], [], ["passed"]],
        "arm": [["passed"], [], [], [], [], [], [], [], [], ["passed"]],
        "riscv": [["passed", "failed"], [], [], ["passed", "blocked"], [], [], [], [], [], ["passed", "passed"]],
        "loong": [[], [], [], [], [], [], [], [], [], ["error"]],
    }
    for age, sha in enumerate(SHAS):
        at = NOW - timedelta(days=age * 3, minutes=18)
        execution = {"repository": "example/asterinas", "workflow_path": ".github/workflows/demo_main.yml", "run_id": str(90000 - age), "attempt": 1, "event": "push", "ref": "refs/heads/main", "source_sha": sha, "tested_sha": sha, "workflow_sha": sha, "base_sha": None, "created_at": stamp(at - timedelta(minutes=40))}
        catalog = record("catalog", f"catalog:demo:{age}")
        catalog.update(source_sha=sha, completeness="complete", gaps=[], platforms=[{"arch": p["arch"], "platform": p["platform"], "scope": "build_only" if p["id"] == "loong" else "configured", "notes": p["note"]} for p in PLATFORMS], entries=[])
        plan = record("plan", f"plan:demo:{age}")
        plan.update(catalog_id=catalog["record_id"], execution=execution, verification_policy=POLICY, selector={"version": "demo-selector-v1", "rules_digest": digest("demo-rules"), "changed_files_digest": None, "status": "ok", "fallback_full": False}, entries=[])
        snapshot = record("snapshot", f"snapshot:demo:{age}")
        snapshot.update(generation_id=f"demo-generation-{age}", main_sha=sha, main_observed_at=stamp(at + timedelta(minutes=14)), as_of=stamp(at + timedelta(minutes=15)), generated_at=stamp(at + timedelta(minutes=16)), catalog_id=catalog["record_id"], api_declarations_id="api:demo", verification_policy=POLICY, required_status="unknown", counts={}, rows=[], ingestions=[], gaps=["All records in this preview are fictional, not actual executions or project support declarations."])
        jobs = 0
        workflow_plans = {}

        def add_entry(suite, platform, index, status, performance=False):
            nonlocal jobs
            jobs += 1
            config = config_for(platform, index, suite["id"])
            if performance:
                config["smp"] = 8
            workflow = "benchmark_x86_tdx" if performance and platform["id"] == "tdx" else "benchmark_x86" if performance else "test_x86_tdx" if platform["id"] == "tdx" else "test_riscv" if platform["id"] == "riscv" else "test_loongarch" if platform["id"] == "loong" else "test_x86"
            if suite["id"] == "nixos":
                workflow = "test_nixos_full" if index else "test_nixos_minimal"
            if suite["id"] == "fs/xfstests" and index:
                workflow = "test_xfstests_full"
            event = "schedule" if performance or platform["id"] == "tdx" or workflow == "test_xfstests_full" else "push"
            if workflow not in workflow_plans:
                local_plan = copy.deepcopy(plan)
                local_plan["record_id"] = f"plan:demo:{age}:{workflow}"
                local_plan["execution"].update(workflow_path=f".github/workflows/{workflow}.yml", run_id=str(90000 - age * 100 + len(workflow_plans)), event=event)
                workflow_plans[workflow] = local_plan
            active_plan = workflow_plans[workflow]
            active_execution = active_plan["execution"]
            config_id = f"{platform['id']}-{config['profile']}-smp{config['smp']}-{index + 1}"
            identity = f"{age}:{suite['id']}:{config_id}"
            entry = {"test_id": suite["id"], "config_id": config_id, "suite": suite["id"], "label": suite["name"], "check_kind": "performance" if performance else suite["kind"], "workflow_path": active_execution["workflow_path"], "primary_event": event, "config": config, "config_digest": digest(config), "cadence": "daily" if event == "schedule" else "on_change", "metric_ids": [m["id"] for m in METRICS] if performance else [], "sources": [source(sha, active_execution["workflow_path"])]}
            catalog["entries"].append(entry)
            selected = "not_selected" if status == "not_selected" else "selected"
            group = f"initramfs/{platform['id']}/{config['profile']}/smp{config['smp']}/{config['boot_protocol']}"
            if suite["id"] == "nixos":
                group = f"nixos/{platform['id']}/{'full' if index else 'minimal'}"
            reason = {"not_selected": "This change did not match the full NixOS rules; candidate scope is preserved.", "blocked": "smoke.boot failed for the same profile; LTP did not run.", "unknown": "No scheduled report for the current commit yet; the latest result is historical context.", "missing_report": "Execution is terminal; a complete report is still missing after 10 minutes.", "cancelled": "The run was cancelled; guest reports that were not uploaded cannot be recovered.", "running": "This configuration is running; a final test outcome is not available yet.", "failed": "An example test assertion failed. See the native cases and evidence.", "error": "Example build preparation failed; this does not establish runtime API incompatibility."}.get(status, "Effective configuration and identity verified; the complete suite passed (example).")
            dependencies = [] if suite["id"] in ("build", "boot", "nixos") or performance else [f"{group}/smoke.lint", f"{group}/smoke.boot"]
            active_plan["entries"].append({"test_id": suite["id"], "config_id": config_id, "selection": selected, "reason_code": "demo_path_rule" if selected == "not_selected" else "demo_full_scope", "reason": reason, "execution_policy": "none" if selected == "not_selected" else "run", "carried_report_id": None, "depends_on": dependencies, "required": None})
            result["presentation"]["groups"][f"{suite['id']}|{config_id}"] = {"group": group}
            report = None
            if status in ("passed", "failed", "error"):
                report = record("report", f"report:{identity}")
                env = environment()
                report.update(plan_id=active_plan["record_id"], execution=copy.deepcopy(active_execution), job_id=str(70000 + age * 1000 + jobs), test_id=suite["id"], config_id=config_id, config=config, config_digest=digest(config), environment=env, environment_id=digest(env), build=None, outcome=status, phase="build" if suite["kind"] == "build" else "test", result_complete=status != "error", reason=reason, started_at=stamp(at - timedelta(minutes=12)), completed_at=stamp(at), collected_at=stamp(at), produced_at=stamp(at + timedelta(seconds=5)), evidence=[{"kind": "log", "url": f"https://example.invalid/actions/runs/{active_execution['run_id']}/job/{70000 + age * 1000 + jobs}", "digest": digest(identity), "expires_at": stamp(at + timedelta(days=30)), "availability": "available"}], measurements=[], comparison=None, case_summary=None)
                if suite["id"] in ("regression", "conformance/ltp", "nixos"):
                    failed = int(status == "failed")
                    report["case_summary"] = {"expected": 24, "passed": 23 if failed else 24, "failed": failed, "skipped": 0, "not_run": 0, "scope": "24 cases in a fictional native report; counts must not be combined across suites."}
                    result["presentation"]["cases"][report["record_id"]] = [{"name": name, "status": "failed" if failed and case == 2 else "passed", "duration": f"{0.12 + case * 0.07:.2f} s"} for case, name in enumerate(["open_create_close", "read_write_roundtrip", "futex_wake_wait", "mmap_anonymous", "process_exit_status"])]
                if performance:
                    report["comparison"] = {"status": "unknown", "rule_version": "demo-paired-v1", "reasons": ["Each metric is checked against paired measurements and environment details; boot lacks a Linux measurement."]}
                    for metric in METRICS:
                        for system, value in zip(("asterinas", "linux"), metric["values"]):
                            if value is not None:
                                value = round(value * (1 + age * 0.03) * (1.18 if platform["id"] == "tdx" else 1), 3)
                            report["measurements"].append({"metric_id": metric["id"], "system": system, "state": "missing" if value is None else "measured", "value": value, "unit": metric["unit"], "raw_unit": metric["unit"], "unit_conversion": "identity", "direction": metric["direction"], "collected_at": stamp(at) if value is not None else None, "comparison_group": f"demo-{identity}", "method_version": "demo-paired-v1", "source": source(sha, f"test/benchmark/{metric['id']}.yaml"), "reason": "Linux measurement unavailable (example)" if value is None else None})
                result["reports"].append(report)
            state = status if status in ("running", "cancelled", "blocked") else "skipped" if status == "not_selected" else "unknown" if status == "unknown" else "completed"
            gates = [{"gate_id": dependencies[-1], "state": "failed", "url": "https://example.invalid/smoke"}] if status == "blocked" else []
            observation = {"execution": active_execution, "job_id": str(70000 + age * 1000 + jobs), "observed_at": stamp(at + timedelta(minutes=15)), "created_at": active_execution["created_at"], "started_at": stamp(at - timedelta(minutes=12)) if state != "skipped" else None, "completed_at": stamp(at) if state in ("completed", "cancelled") else None, "status": state, "conclusion": status if state == "completed" else None, "url": f"https://example.invalid/actions/runs/{active_execution['run_id']}", "gate_observations": gates, "reason": reason}
            current = {"plan_id": active_plan["record_id"], "report_id": report["record_id"] if report else None, "selection": selected, "execution": state, "report_state": "received" if report else "not_expected" if selected == "not_selected" or status == "blocked" else "missing" if status in ("missing_report", "cancelled") else "pending", "status": status, "observation": observation, "reason": reason, "evidence": []}
            latest = None if report is None else {key: report[key] for key in ("collected_at", "config_digest", "environment_id", "outcome")}
            if latest:
                latest.update(report_id=report["record_id"], source_sha=sha, tested_sha=sha)
            snapshot["rows"].append({"test_id": suite["id"], "config_id": config_id, "current": current, "latest_result": latest, "freshness": "not_applicable" if entry["cadence"] != "daily" else "fresh" if latest else "unknown"})

        for platform in PLATFORMS:
            for suite, statuses in zip(SUITES, layout[platform["id"]]):
                for index, status in enumerate(statuses):
                    add_entry(suite, platform, index, "passed" if age else status)
        for platform in PLATFORMS[:2]:
            add_entry({"id": "benchmark", "name": "Benchmark", "kind": "performance"}, platform, 0, "passed", performance=True)
        statuses = [row["current"]["status"] for row in snapshot["rows"]]
        snapshot["counts"] = {"expected": len(statuses), "selected": sum(row["current"]["selection"] == "selected" for row in snapshot["rows"]), "received": sum(row["current"]["report_id"] is not None for row in snapshot["rows"]), "passed": statuses.count("passed"), "failed": statuses.count("failed"), "unresolved": len(statuses) - statuses.count("passed") - statuses.count("failed")}
        result["catalogs"].append(catalog)
        result["plans"].extend(workflow_plans.values())
        result["snapshots"].append(snapshot)

    # A previous report can remain useful without verifying the current main.
    old_rows = {(r["test_id"], r["config_id"]): r for r in result["snapshots"][1]["rows"]}
    for row in result["snapshots"][0]["rows"]:
        if row["latest_result"] is None:
            row["latest_result"] = copy.deepcopy(old_rows[(row["test_id"], row["config_id"])]["latest_result"])
            if row["freshness"] == "unknown":
                row["freshness"] = "stale"
    api = record("api_declarations", "api:demo")
    api.update(source_sha=SHAS[0], generated_at=stamp(NOW - timedelta(hours=2)), completeness="partial", gaps=["Fictional API subset for interface exploration, not project support declarations.", "Detailed declarations for non-x86 architectures are not included in this demo."], entries=[])
    calls = [("read", "File I/O", "supported", []), ("write", "File I/O", "supported", []), ("openat", "File I/O", "partial", ["O_TMPFILE not assessed (fictional limitation)"]), ("close", "File I/O", "supported", []), ("statx", "File I/O", "partial", ["Extended fields partially supported (fictional limitation)"]), ("mmap", "Memory", "partial", ["Some mapping flags are unsupported (fictional limitation)"]), ("mprotect", "Memory", "supported", []), ("munmap", "Memory", "supported", []), ("clone", "Processes & scheduling", "partial", ["Namespace flags are outside the support scope of this example"]), ("execve", "Processes & scheduling", "supported", []), ("futex", "Processes & scheduling", "partial", ["Priority inheritance modes not assessed (fictional limitation)"]), ("sched_yield", "Processes & scheduling", "supported", []), ("socket", "Networking", "partial", ["Only AF_INET / AF_UNIX examples are shown"]), ("epoll_wait", "Networking", "supported", []), ("io_uring_setup", "Async I/O", "unsupported", ["Fictional unsupported state to illustrate the interface"]), ("landlock_create_ruleset", "Security", "not_assessed", ["No detailed declaration yet (example)"])]
    for name, category, status, limitations in calls:
        sources = [source(SHAS[0], "book/src/kernel/linux-compatibility/README.md")]
        flags = []
        if name in ("mmap", "openat", "clone", "futex"):
            names = {"mmap": ["MAP_PRIVATE", "MAP_SHARED", "MAP_HUGETLB"], "openat": ["O_RDONLY", "O_CREAT", "O_TMPFILE"], "clone": ["CLONE_VM", "CLONE_FS", "CLONE_NEWNET"], "futex": ["FUTEX_WAIT", "FUTEX_WAKE", "FUTEX_LOCK_PI"]}[name]
            flags = [{"name": flag, "status": "supported" if index < 2 else "not_assessed", "limitations": [] if index < 2 else ["Unassessed fictional example"], "sources": sources} for index, flag in enumerate(names)]
        api["entries"].append({"api_id": f"linux/syscall/{name}", "arch": "x86_64", "category": category, "name": name, "number": None, "status": status, "limitations": limitations, "flag_completeness": "partial" if flags else "not_assessed", "flags": flags, "sources": sources, "evidence_ids": []})
    result["api_declarations"].append(api)
    old_api = copy.deepcopy(api)
    old_api.update(record_id="api:demo:1", source_sha=SHAS[1], generated_at=stamp(NOW - timedelta(days=3, hours=2)))
    for entry in old_api["entries"]:
        entry["sources"] = [source(SHAS[1], item["path"]) for item in entry["sources"]]
        for flag in entry["flags"]:
            flag["sources"] = [source(SHAS[1], item["path"]) for item in flag["sources"]]
    result["api_declarations"].append(old_api)
    result["snapshots"][1]["api_declarations_id"] = old_api["record_id"]
    for metric in METRICS:
        for platform in ("x86", "tdx"):
            points = []
            for day in range(13, -1, -1):
                missing = day == 7
                changed = day < 5
                factor = 1 if day == 0 else 1.03 if day == 3 else 1 + day * 0.007 + ((day % 3) - 1) * 0.015
                linux_factor = factor if day in (0, 3) else 1 + (day % 2) * 0.015
                points.append({"at": stamp(NOW - timedelta(days=day, minutes=18)), "source_sha": SHAS[0] if day == 0 else SHAS[1] if day == 3 else hashlib.sha1(f"demo-day-{day}".encode()).hexdigest(), "config_id": f"{platform}-release-smp8-1", "config_digest": digest(config_for(PLATFORMS[0 if platform == 'x86' else 1], 0, "benchmark") | {"smp": 8}), "method_version": "demo-paired-v1", "environment_id": "demo-env-b" if changed else "demo-env-a", "asterinas": None if missing else round(metric["values"][0] * factor * (1.18 if platform == "tdx" else 1), 3), "linux": None if missing or metric["values"][1] is None else round(metric["values"][1] * linux_factor * (1.18 if platform == "tdx" else 1), 3)})
            result["presentation"]["history"].append({"metric_id": metric["id"], "platform": platform, "points": points})
    (ROOT / "data/demo.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (ROOT / "data/boot-example.log").write_text("DEMO ONLY — fictional boot log, not a real Asterinas execution.\n[host] final checkout: " + SHAS[0] + "\n[host] RELEASE=1 SMP=1 ENABLE_KVM=1\n[smoke.compile] exit=0\n[guest] boot_hello: success\n[host] exit=0 result_complete=true\n")
    print(f"Generated {len(result['catalogs'])} catalogs, {len(result['reports'])} reports, {len(result['snapshots'])} snapshots.")


if __name__ == "__main__":
    main()
