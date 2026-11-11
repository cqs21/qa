#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0

"""Check schema and cross-record invariants of the preview fixture."""

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def digest(value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1] / "data"
    schema = json.loads((root / "schema-v1.json").read_text())
    data = json.loads((root / "demo.json").read_text())
    records = [record for kind in ("catalogs", "plans", "reports", "api_declarations", "snapshots") for record in data[kind]]
    by_id = {record["record_id"]: record for record in records}
    assert len(by_id) == len(records), "duplicate record IDs"
    for record in records:
        assert record["kind"] in schema["$defs"], "unknown record kind"
        validator = Draft202012Validator({"$defs": schema["$defs"], "$ref": f"#/$defs/{record['kind']}"}, format_checker=FormatChecker())
        for error in validator.iter_errors(record):
            path = "/".join(str(part) for part in error.absolute_path)
            raise AssertionError(f"{record['record_id']} at {path}: {error.message}")
        assert record["example"] is True, "unmarked example record"
    for catalog in data["catalogs"]:
        entries = {(entry["test_id"], entry["config_id"]): entry for entry in catalog["entries"]}
        assert len(entries) == len(catalog["entries"]), "duplicate catalog identity"
        for entry in entries.values():
            assert entry["config_digest"] == digest(entry["config"]), "incorrect config digest"
        for plan in (plan for plan in data["plans"] if plan["catalog_id"] == catalog["record_id"]):
            expected = {key for key, entry in entries.items() if entry["workflow_path"] == plan["execution"]["workflow_path"]}
            assert expected == {(entry["test_id"], entry["config_id"]) for entry in plan["entries"]}, "plan shrank its candidate scope"
    for report in data["reports"]:
        plan = by_id[report["plan_id"]]
        assert report["execution"] == plan["execution"], "report/plan execution mismatch"
        assert report["config_digest"] == digest(report["config"]), "report config mismatch"
        assert report["environment_id"] == digest(report["environment"]), "environment mismatch"
        if report["outcome"] == "passed":
            assert report["result_complete"] and report["evidence"], "incomplete pass"
            assert report["started_at"] and report["completed_at"] and report["collected_at"]
        for measurement in report["measurements"]:
            assert (measurement["value"] is None) == (measurement["state"] != "measured"), "missing value invented"
    for snapshot in data["snapshots"]:
        catalog = by_id[snapshot["catalog_id"]]
        assert by_id[snapshot["api_declarations_id"]]["generated_at"] <= snapshot["as_of"], "snapshot references a future declaration"
        expected = {(entry["test_id"], entry["config_id"]) for entry in catalog["entries"]}
        assert expected == {(row["test_id"], row["config_id"]) for row in snapshot["rows"]}
        statuses = [row["current"]["status"] for row in snapshot["rows"]]
        counts = snapshot["counts"]
        assert counts["expected"] == len(expected)
        assert counts["passed"] == statuses.count("passed")
        assert counts["failed"] == statuses.count("failed")
        assert counts["expected"] == counts["passed"] + counts["failed"] + counts["unresolved"]
        assert counts["received"] == sum(row["current"]["report_id"] is not None for row in snapshot["rows"])
        assert counts["selected"] == sum(row["current"]["selection"] == "selected" for row in snapshot["rows"])
        assert snapshot["required_status"] == "unknown", "provisional policy became passed"
        for row in snapshot["rows"]:
            current = row["current"]
            if current["report_id"]:
                report = by_id[current["report_id"]]
                assert current["plan_id"] == report["plan_id"]
                assert current["status"] == report["outcome"]
            if current["status"] == "passed":
                assert report["execution"]["source_sha"] == report["execution"]["tested_sha"] == snapshot["main_sha"]
            if row["latest_result"]:
                latest = row["latest_result"]
                report = by_id[latest["report_id"]]
                assert latest["collected_at"] == report["collected_at"]
                assert latest["source_sha"] == report["execution"]["source_sha"]
                assert latest["config_digest"] == report["config_digest"]
    for history in data["presentation"]["history"]:
        for snapshot in data["snapshots"]:
            point = next(point for point in history["points"] if point["source_sha"] == snapshot["main_sha"])
            report = next(report for report in data["reports"] if report["test_id"] == "benchmark" and report["execution"]["source_sha"] == snapshot["main_sha"] and report["config_id"].startswith(history["platform"] + "-"))
            assert point["config_digest"] == report["config_digest"]
            for system in ("linux", "asterinas"):
                measurement = next(item for item in report["measurements"] if item["metric_id"] == history["metric_id"] and item["system"] == system)
                assert point[system] == measurement["value"], "history and original measurement differ"
    print(f"PASS: {len(records)} schema-valid records; identity, scope, counts, timestamps and performance history agree.")


if __name__ == "__main__":
    main()
