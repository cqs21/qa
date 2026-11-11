#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Check archived provenance and the parser boundaries that affect conclusions."""

import datetime as dt
import hashlib
import json
import unittest

from import_real import Archive, QA, clean_log, execution_origin, native_summary, parse_api, parse_benchmarks, parse_job
import main_results


class MainHistory(unittest.TestCase):
    def record(self, job_id, run_id, conclusion="success", config="boot", attempt=1, **overrides):
        return {"id": str(job_id), "origin_job_id": str(job_id), "config_key": config,
                "suite": config, "platform": "x86", "conclusion": conclusion, "status": "completed",
                "execution_attempt": attempt, "started_at": f"2026-11-{run_id:02d}T00:00:00Z",
                "steps": [{"started_at": f"2026-11-{run_id:02d}T00:00:00Z", "conclusion": conclusion}],
                "run": {"id": run_id, "created_at": f"2026-11-{run_id:02d}T00:00:00Z"}, **overrides}

    def test_only_completed_main_events_from_original_repository_are_eligible(self):
        run = {"status": "completed", "head_branch": "main", "event": "push",
               "head_repository": {"full_name": "asterinas/asterinas"}}
        for event in ("push", "schedule", "workflow_dispatch"):
            self.assertTrue(main_results.eligible({**run, "event": event}, "asterinas/asterinas"))
        for overrides in ({"event": "pull_request"}, {"event": "pull_request_target"},
                          {"head_branch": "feature"}, {"status": "in_progress"},
                          {"head_repository": {"full_name": "fork/asterinas"}}, {"head_repository": None}):
            with self.subTest(overrides=overrides):
                self.assertFalse(main_results.eligible({**run, **overrides}, "asterinas/asterinas"))

    def test_partial_run_keeps_other_configurations_and_latest_failure(self):
        records = [self.record(11, 1), self.record(12, 1, config="nixos/hello"),
                   self.record(21, 2, "failure"), self.record(31, 3, "failure")]
        results = {row["key"]: row for row in main_results.aggregate(records)}
        self.assertEqual(results["boot"]["latest"], "31")
        self.assertEqual(results["boot"]["previous_success"], "11")
        self.assertEqual(results["nixos/hello"]["latest"], "12")
        self.assertIsNone(results["nixos/hello"]["previous_success"])
        self.assertEqual(main_results.aggregate(list(reversed(records))), main_results.aggregate(records))

    def test_previous_success_is_distinct_and_not_previous_failure(self):
        records = [self.record(11, 1), self.record(21, 2, "failure"), self.record(31, 3)]
        result, = main_results.aggregate(records)
        self.assertEqual((result["latest"], result["previous_success"]), ("31", "11"))

    def test_rerun_and_late_arrival_order_uses_run_creation_then_attempt(self):
        records = [self.record(11, 1, started_at="2026-11-20T00:00:00Z"),
                   self.record(21, 2), self.record(22, 2, "failure", attempt=2)]
        result, = main_results.aggregate(records)
        self.assertEqual((result["latest"], result["previous_success"]), ("22", "21"))

    def test_skipped_and_unexecuted_cancelled_jobs_do_not_replace_results(self):
        records = [self.record(11, 1), self.record(21, 2, "skipped"),
                   self.record(31, 3, "cancelled", steps=[]),
                   self.record(41, 4, "cancelled", steps=[{"started_at": None, "conclusion": "skipped"}]),
                   self.record(51, 5, "failure", status="in_progress")]
        result, = main_results.aggregate(records)
        self.assertEqual(result["latest"], "11")
        records.append(self.record(61, 6, "cancelled"))
        result, = main_results.aggregate(records)
        self.assertEqual((result["latest"], result["previous_success"]), ("61", "11"))

    def test_nixos_selectors_are_not_suites_and_architectures_stay_separate(self):
        path = ".github/workflows/test_nixos_full.yml"
        self.assertIsNone(main_results.test_suite(path, "Select suites"))
        self.assertEqual(main_results.test_suite(path, "Test nginx"), "nixos/nginx")
        self.assertEqual(main_results.platform(path, "Test nginx"), "x86")
        self.assertEqual(main_results.platform(".github/workflows/test_x86.yml", "cross-compile-test (aarch64)"), "arm")
        self.assertEqual(main_results.platform(".github/workflows/test_aarch64.yml", "boot (ubuntu-latest)"), "arm")


class ParserBoundaries(unittest.TestCase):
    def test_rerun_clones_keep_original_execution(self):
        original = {"id": 101, "name": "basic-test (lint)", "run_attempt": 1,
                    "started_at": "2026-11-01T00:00:00Z", "completed_at": "2026-11-01T00:01:00Z", "conclusion": "success"}
        clone = {**original, "id": 202, "run_attempt": 2}
        previous = [{"jobs": [original]}]
        self.assertEqual(execution_origin(clone, previous)["id"], 101)
        real_rerun = {**clone, "started_at": "2026-11-01T01:00:00Z", "completed_at": "2026-11-01T01:01:00Z"}
        self.assertEqual(execution_origin(real_rerun, previous)["id"], 202)

    def test_missing_and_build_failure_are_not_zero_tests(self):
        self.assertIsNone(native_summary([], "kernel/ktest"))
        self.assertIsNone(native_summary(["error: could not compile `unwinding`"], "kernel/ktest"))

    def test_rust_ignored_counts_and_repeated_harnesses(self):
        lines = clean_log("2026-11-01T01:00:00.123Z test result: \x1b[32mok\x1b[0m. 2 passed; 0 failed; 3 ignored; 0 measured; 0 filtered out\n"
                          "test result: FAILED. 1 passed; 1 failed; 0 filtered out.")
        self.assertEqual(native_summary(lines, "kernel/ktest")["counts"], {"passed": 3, "failed": 1, "ignored": 3})

    def test_gtest_skip_detail_is_not_double_counted(self):
        lines = ["[==========] 4 tests from 1 test suite ran. (3 ms total)", "[  PASSED  ] 2 tests.",
                 "[  SKIPPED ] 2 tests, listed below:", "[  SKIPPED ] XattrTest.Security (0 ms)",
                 "[  SKIPPED ] XattrTest.Trusted"]
        self.assertEqual(native_summary(lines, "conformance/gvisor")["counts"], {"passed": 2, "skipped": 2, "ran": 4})

    def test_tap_assertions_are_not_certified_passes(self):
        summary = native_summary(["Files=232, Tests=6656, 178 wallclock secs", "Result: PASS"], "fs/pjdfstest")
        self.assertEqual(summary["counts"], {"files": 232, "assertions": 6656})
        self.assertNotIn("passed", summary["counts"])

    def test_nixos_uses_final_host_summary_not_nested_output(self):
        lines = ["=== Found 4 test case(s) ===", "Passed: 900", "Failed: 23",
                 "✓ Test case 'nginx_serve_webpage' passed", "=== Test Summary ===", "Passed: 4", "Failed: 0"]
        summary = native_summary(lines, "nixos/web-servers-and-proxies")
        self.assertEqual(summary["counts"], {"passed": 4, "failed": 0})
        self.assertIn("top-level", summary["scope"])

    def test_nixos_missing_or_incomplete_summary_stays_unknown(self):
        for lines in (["error: could not compile"], ["Passed: 4", "Failed: 0"],
                      ["=== Test Summary ===", "Passed: 4"], ["✓ Test case 'hello' passed"]):
            self.assertIsNone(native_summary(lines, "nixos/hello"))

    def test_nixos_failures_and_repeated_summaries_keep_final_counts(self):
        lines = ["=== Test Summary ===", "Passed: 4", "Failed: 0", "Another invocation",
                 "=== Test Summary ===", "Passed: 2", "Failed: 1", "Failed tests:", "  - nginx"]
        self.assertEqual(native_summary(lines, "nixos/web-servers-and-proxies")["counts"], {"passed": 2, "failed": 1})


class SourceIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = Archive()
        cls.data = json.loads((QA / "data/real.json").read_text())

    def test_every_archived_source_has_original_digest(self):
        self.assertEqual(self.data["sources"], self.archive.manifest["sources"])
        for source in self.data["sources"]:
            if source.get("cache"):
                with self.subTest(source=source["id"]):
                    raw = self.archive.text(source["id"]).encode()
                    self.assertEqual(len(raw), source["bytes"])
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), source["sha256"])

    def test_job_lists_are_complete_and_log_links_point_to_execution(self):
        for snapshot in self.data["snapshots"]:
            with self.subTest(run=snapshot["run_id"]):
                raw = self.archive.json(f"jobs-{snapshot['run_id']}-{snapshot['attempt']}.json")
                self.assertEqual(len(snapshot["jobs"]), raw["total_count"])
                self.assertEqual({job["id"] for job in snapshot["jobs"]}, {str(job["id"]) for job in raw["jobs"]})
                for job in snapshot["jobs"]:
                    self.assertIn(f"/job/{job['origin_job_id']}", job["url"])
                    self.assertLessEqual(job["execution_attempt"], job["listed_attempt"])
                    if job["inherited"]:
                        self.assertLess(job["execution_attempt"], job["listed_attempt"])
                        self.assertNotEqual(job["id"], job["origin_job_id"])
                    if job["log_source_id"]:
                        self.assertEqual(job["log_source_id"], f"job-{job['origin_job_id']}.log")
                    if job["native_summary"]:
                        self.assertTrue(job["log_source_id"])
                        self.assertTrue(all(isinstance(count, int) and count >= 0 for count in job["native_summary"]["counts"].values()))

    def test_book_has_supported_syscalls_with_partial_flags(self):
        api = self.data["api"]
        entries = api["entries"]
        self.assertEqual(len(entries), len({entry["number"] for entry in entries}))
        mmap = next(entry for entry in entries if entry["name"] == "mmap")
        self.assertTrue(mmap["declared_supported"])
        self.assertEqual(mmap["status"], "partial")
        self.assertEqual(mmap["number"], 9)
        self.assertIn("Silently-ignored flags:", mmap["details"])
        self.assertIn("MAP_HUGETLB", mmap["details"])
        self.assertIn(api["source_sha"], mmap["url"])
        self.assertTrue(all(entry["arch"] == "x86_64" for entry in entries))
        self.assertTrue(all(entry["declared_supported"] for entry in entries if entry["status"] == "partial"))

    def test_benchmark_units_raw_values_and_unknown_identity(self):
        for metric in self.data["metrics"]:
            points = metric["points"]
            source = self.archive.entries[metric["source_id"]]
            self.assertEqual(points, sorted(points, key=lambda point: point["at"]))
            self.assertIn(self.data["benchmark_sha"], metric["url"])
            for point in points:
                self.assertIsNone(point["tested_sha"])
                self.assertIsNone(point["environment_id"])
                self.assertIsNone(point["run_id"])
                for system in ("asterinas", "linux"):
                    measurement = point[system]
                    if measurement["value"] is not None:
                        self.assertEqual(measurement["value"], float(measurement["raw_value"]))
                self.assertLessEqual(dt.datetime.fromisoformat(point["at"].replace("Z", "+00:00")),
                                     dt.datetime.fromisoformat(source["observed_at"].replace("Z", "+00:00")))
        boot = next(metric for metric in self.data["metrics"] if metric["id"] == "boot_lat")
        self.assertTrue(all(point["asterinas"]["unit"] == "sec" for point in boot["points"]))

    def test_offline_rebuild_matches_pinned_sources(self):
        self.assertEqual(parse_benchmarks(self.archive), self.data["metrics"])
        self.assertEqual(parse_api(self.archive.json("book.json"), self.data["api"]["source_sha"]), self.data["api"])
        self.assertEqual(main_results.build(self.archive, parse_job, execution_origin), self.data["main_results"])

    def test_main_catalog_and_execution_provenance(self):
        ci = self.data["main_results"]
        workflows = {workflow["id"]: workflow for workflow in ci["workflows"]}
        records = {record["id"]: record for record in ci["records"]}
        for workflow in workflows.values():
            self.assertEqual(workflow["state"], "active")
            self.assertTrue(workflow["path"] in ci["definition_paths"] or workflow["path"].startswith("dynamic/"))
            if workflow["latest"]:
                raw = self.archive.json(f"run-{workflow['latest']['id']}.json")
                self.assertTrue(main_results.eligible(raw, ci["repository"]))
                self.assertEqual(workflow["latest"], main_results.run_identity(raw))
        for record in records.values():
            with self.subTest(job=record["id"]):
                run = self.archive.json(f"run-{record['run']['id']}.json")
                self.assertTrue(main_results.eligible(run, ci["repository"]))
                self.assertIn(record["workflow_id"], workflows)
                self.assertIn(f"/job/{record['origin_job_id']}", record["url"])
                raw_jobs = self.archive.json(f"jobs-{run['id']}-{record['execution_attempt']}.json")["jobs"]
                origin = next(job for job in raw_jobs if str(job["id"]) == record["origin_job_id"])
                self.assertEqual(origin["conclusion"], record["conclusion"])
                self.assertEqual(origin["completed_at"], record["completed_at"])
                self.assertEqual(origin["head_sha"], run["head_sha"])
        for result in ci["results"]:
            latest = records[result["latest"]]
            self.assertEqual(result["key"], latest["config_key"])
            if result["previous_success"]:
                previous = records[result["previous_success"]]
                self.assertEqual(previous["conclusion"], "success")
                self.assertEqual(previous["config_key"], latest["config_key"])
                self.assertNotEqual(previous["origin_job_id"], latest["origin_job_id"])
                self.assertLess(main_results.execution_order(previous), main_results.execution_order(latest))
        self.assertTrue(any(result["suite"].startswith("nixos/") for result in ci["results"]))

if __name__ == "__main__":
    unittest.main(verbosity=2)
