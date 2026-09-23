"""Contract and provenance checks for the hand-curated S02 UI fixtures."""

import json
import re
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "backend/app/mocks/demo_report.json"
WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_clauses(path):
    """Read printed clause numbers and exact text, including lettered subparagraphs."""
    with ZipFile(path) as archive:
        document = ElementTree.fromstring(archive.read("word/document.xml"))
    clauses = {}
    current = None
    section = ""
    for index, paragraph in enumerate(document.iter(f"{WORD}p")):
        text = "".join(node.text or "" for node in paragraph.iter(f"{WORD}t")).strip()
        if not text:
            continue
        # The supplied DOCX sometimes puts the next numbered clause in the same paragraph.
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
            elif current:
                clauses[current]["text"] += "\n" + part
    return clauses


def load_report():
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


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


def test_report_contract():
    from app import schemas

    report = load_report()
    report_model = getattr(schemas, "Report", None)
    if report_model is not None:
        report_model.model_validate(report)
    else:
        assert set(report) == {
            "run_id",
            "created_at",
            "documents",
            "unit_changes",
            "function_matches",
            "duplicates",
            "conflicts",
            "conclusion_md",
            "stats",
        }
    # FunctionMatch and Duplicate carry sources on their nested Function objects (§3).
    for collection in ("unit_changes", "function_matches", "duplicates", "conflicts"):
        for finding in report[collection]:
            assert list(walk_sources(finding)), f"Unsourced {collection} finding"


def test_sources_are_verbatim_in_the_claimed_docx_clause():
    report = load_report()
    documents = {doc["id"]: doc for doc in report["documents"]}
    originals = {
        doc["id"]: docx_clauses(ROOT / "data/case11" / doc["name"]) for doc in report["documents"]
    }
    for source in walk_sources(report):
        doc = documents[source["doc_id"]]
        assert source["doc_name"] == doc["name"]
        assert source["version"] == doc["version"]
        original = originals[doc["id"]][source["clause_number"]]
        assert source["quote"].strip()
        assert source["quote"] in original["text"], source
        embedded = {clause["number"]: clause for clause in doc["clauses"]}
        assert embedded[source["clause_number"]]["text"] == original["text"]
        assert embedded[source["clause_number"]]["index"] == original["index"]


def test_frontend_report_is_identical():
    frontend = (ROOT / "frontend/lib/fixtures/report.ts").read_text(encoding="utf-8")
    payload = frontend.split("export const demoReport: Report = ", 1)[1].split(";\n", 1)[0]
    assert json.loads(payload) == load_report()


def test_findings_have_consistent_versions_and_unit_references():
    report = load_report()
    units = {}
    for change in report["unit_changes"]:
        for side, version in (("unit_before", "before"), ("unit_after", "after")):
            if unit := change[side]:
                units[unit["id"]] = unit
                assert unit["version"] == version
    assert Counter(item["status"] for item in report["unit_changes"]) == {
        "kept": 1,
        "transformed": 1,
        "created": 1,
    }
    assert Counter(item["status"] for item in report["function_matches"]) == {
        "kept": 2,
        "changed": 2,
        "lost": 2,
        "new": 2,
        "moved": 2,
    }

    def check_function(function, version=None):
        unit = units[function["unit_id"]]
        assert function["sources"]
        assert function["text"] and function["signature"]
        assert all(s["version"] == unit["version"] for s in function["sources"])
        if version:
            assert unit["version"] == version

    matched_ids = set()
    for match in report["function_matches"]:
        assert 0 <= match["confidence"] <= 1
        assert (match["before"] is None) == (match["status"] == "new")
        assert (match["after"] is None) == (match["status"] == "lost")
        for side in ("before", "after"):
            if function := match[side]:
                check_function(function, side)
                assert function["id"] not in matched_ids
                matched_ids.add(function["id"])
        if match["status"] == "moved":
            before = units[match["before"]["unit_id"]]
            after = units[match["after"]["unit_id"]]
            assert before["name"] != after["name"]
    for duplicate in report["duplicates"]:
        assert 0 <= duplicate["similarity"] <= 1
        a, b = duplicate["function_a"], duplicate["function_b"]
        check_function(a, "after")
        check_function(b, "after")
        assert a["unit_id"] != b["unit_id"]
    for conflict in report["conflicts"]:
        assert conflict["rule_id"] and conflict["explanation"]
        assert conflict["units"] and conflict["functions"]
        for function in conflict["functions"]:
            check_function(function, "after")


def test_stats_and_conclusion_are_consistent():
    report = load_report()
    assert len(report["conclusion_md"].splitlines()) == 10
    expected = {
        key: len(report[key])
        for key in ("documents", "unit_changes", "function_matches", "duplicates", "conflicts")
    }
    expected.update(Counter(item["status"] for item in report["function_matches"]))
    assert report["stats"] == expected
    assert len(report["duplicates"]) == 2
    assert len(report["conflicts"]) == 1


def test_run_fixtures():
    from app import schemas

    frontend = (ROOT / "frontend/lib/fixtures/run.ts").read_text(encoding="utf-8")
    payload = frontend.split("export const demoRuns: RunStatus[] = ", 1)[1].split(";\n", 1)[0]
    runs = json.loads(payload)
    assert [(run["status"], run["progress"]) for run in runs] == [
        ("parsing", 20),
        ("matching", 70),
        ("done", 100),
    ]
    model = getattr(schemas, "RunStatus", None)
    if model is not None:
        for run in runs:
            model.model_validate(run)
