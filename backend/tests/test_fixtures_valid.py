"""S02 fixture checks: published S01 contract and real DOCX provenance."""

import json
import re
import subprocess
import sys
import types
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "backend/app/mocks/demo_report.json"
WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_clauses(path):
    with ZipFile(path) as archive:
        document = ElementTree.fromstring(archive.read("word/document.xml"))
    clauses = {}
    current = None
    section = ""
    for index, paragraph in enumerate(document.iter(f"{WORD}p")):
        text = "".join(node.text or "" for node in paragraph.iter(f"{WORD}t")).strip()
        for part in re.split(r" (?=3\.1[012]\.)", text):
            match = re.match(r"^(\d+(?:\.\d+)+)\.\s*(.*)", part)
            if match:
                current = match[1]
                assert current not in clauses, f"Duplicate printed clause {current}"
                clauses[current] = {
                    "number": current,
                    "section": section,
                    "text": part,
                    "index": index,
                }
            elif re.match(r"^\d+\.\s", part):
                section = part
                current = None
            elif current and part:
                clauses[current]["text"] += "\n" + part
    return clauses


def load_report():
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def contract_models():
    """Use merged schema, or published S01 while branches await merge."""
    from app import schemas

    if hasattr(schemas, "Report"):
        return schemas
    try:
        source = subprocess.check_output(
            ["git", "show", "origin/s/contract:backend/app/schemas.py"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return schemas
    snapshot = types.ModuleType("s01_contract_snapshot")
    sys.modules[snapshot.__name__] = snapshot
    exec(compile(source, "origin/s/contract:backend/app/schemas.py", "exec"), vars(snapshot))
    return snapshot


def walk_sources(value):
    if isinstance(value, dict):
        if "sources" in value:
            assert value["sources"], f"Empty sources: {value}"
            yield from value["sources"]
        for key, nested in value.items():
            if key != "sources":
                yield from walk_sources(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from walk_sources(nested)


def test_report_validates_against_s01_contract():
    report = load_report()
    schemas = contract_models()
    if hasattr(schemas, "Report"):
        schemas.Report.model_validate(report)
    else:
        assert set(report) == {
            "run_id",
            "created_at",
            "before_documents",
            "after_documents",
            "unit_changes",
            "function_matches",
            "constraints",
            "duplicates",
            "conflicts",
            "conclusion_md",
            "recommendations",
            "stats",
        }
    for collection in (
        "unit_changes",
        "function_matches",
        "constraints",
        "duplicates",
        "conflicts",
    ):
        for finding in report[collection]:
            assert list(walk_sources(finding)), f"Unsourced {collection} finding"


def test_every_quote_is_in_its_printed_docx_clause():
    report = load_report()
    documents = {doc["id"]: doc for doc in report["before_documents"] + report["after_documents"]}
    originals = {
        doc["id"]: docx_clauses(ROOT / "data/case11" / doc["name"]) for doc in documents.values()
    }
    for source in walk_sources(report):
        doc = documents[source["doc_id"]]
        assert (source["doc_name"], source["version"]) == (doc["name"], doc["version"])
        original = originals[doc["id"]][source["clause_number"]]
        assert source["quote"].strip() and source["quote"] in original["text"], source
        embedded = {clause["id"]: clause for clause in doc["clauses"]}
        clause = embedded[source["clause_id"]]
        assert clause["number"] == source["clause_number"]
        assert (clause["text"], clause["index"]) == (original["text"], original["index"])


def test_frontend_report_is_identical():
    frontend = (ROOT / "frontend/lib/fixtures/report.ts").read_text(encoding="utf-8")
    payload = frontend.split("export const demoReport: Report = ", 1)[1].split(";\n", 1)[0]
    assert json.loads(payload) == load_report()


def test_match_shapes_and_candidate_loss_are_honest():
    report = load_report()
    units = {}
    for change in report["unit_changes"]:
        for side, version in (("unit_before", "before"), ("unit_after", "after")):
            if unit := change[side]:
                units[unit["id"]] = unit
                assert unit["version"] == version
    assert Counter(c["status"] for c in report["unit_changes"]) == {
        "kept": 1,
        "transformed": 1,
        "created": 1,
    }
    assert Counter(m["status"] for m in report["function_matches"]) == {
        "kept": 2,
        "changed": 2,
        "lost": 2,
        "new": 2,
        "moved": 2,
    }
    assert sum(m["kind"] == "split" for m in report["function_matches"]) == 1
    for match in report["function_matches"]:
        assert match["sources"] and 0 <= match["confidence"] <= 1
        assert bool(match["before"]) == (match["status"] != "new")
        assert bool(match["after"]) == (match["status"] != "lost")
        if match["kind"] == "split":
            assert len(match["before"]) == 1 and len(match["after"]) == 2
        if match["status"] == "lost":
            assert match["verified"] is False
            assert "требует проверки" in match["note"]
        for side, version in (("before", "before"), ("after", "after")):
            for function in match[side]:
                assert function["modality"] != "prohibition"
                assert all(s["version"] == version for s in function["sources"])
                if function["unit_id"] is not None:
                    assert units[function["unit_id"]]["version"] == version
    for constraint in report["constraints"]:
        assert constraint["modality"] == "prohibition"
        assert any(s["clause_number"] == "5.8" for s in constraint["sources"])


def test_reference_diff_examples_and_candidate_flags():
    report = load_report()
    assert any(
        s["version"] == "before" and s["clause_number"] == "5.3.6"
        for match in report["function_matches"]
        if match["status"] == "lost"
        for s in match["sources"]
    )
    assert any(
        "информирует о потенциальном конфликте" in s["quote"]
        for match in report["function_matches"]
        if match["status"] == "new"
        for s in match["sources"]
    )
    assert len(report["duplicates"]) == 2 and len(report["conflicts"]) == 1
    assert all(not finding["verified"] for finding in report["duplicates"] + report["conflicts"])


def test_stats_count_only_verified_findings():
    report = load_report()
    assert len(report["conclusion_md"].splitlines()) == 10
    stats = report["stats"]
    schemas = contract_models()
    if hasattr(schemas, "STATS_KEYS"):
        assert set(stats) == set(schemas.STATS_KEYS)
    matches = report["function_matches"]
    assert stats["matches"] == sum(m["verified"] for m in matches)
    assert stats["lost"] == sum(m["verified"] and m["status"] == "lost" for m in matches)
    assert stats["new"] == sum(m["verified"] and m["status"] == "new" for m in matches)
    assert stats["duplicates"] == sum(d["verified"] for d in report["duplicates"])
    assert stats["conflicts"] == sum(c["verified"] for c in report["conflicts"])
    assert stats["unverified_candidates"] == sum(
        not item["verified"]
        for key in ("function_matches", "duplicates", "conflicts")
        for item in report[key]
    )


def test_run_fixtures_follow_s01_contract():
    frontend = (ROOT / "frontend/lib/fixtures/run.ts").read_text(encoding="utf-8")
    payload = frontend.split("export const demoRuns: RunStatus[] = ", 1)[1].split(";\n", 1)[0]
    runs = json.loads(payload)
    assert [(run["status"], run["progress"]) for run in runs] == [
        ("parsing", 5),
        ("verification", 65),
        ("done", 100),
    ]
    assert all(run["run_id"] == load_report()["run_id"] for run in runs)
    schemas = contract_models()
    if hasattr(schemas, "RunStatus"):
        for run in runs:
            schemas.RunStatus.model_validate(run)
