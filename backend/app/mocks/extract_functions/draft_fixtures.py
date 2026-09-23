"""Черновые mock-фикстуры `extract_functions` для тестового комплекта (S09, до живого прогона).

Это НЕ ответы модели: правила ниже раскладывают пункты разделов 2, 4, 5 редакций 8 и 9 на
функции в формате живого ответа (`ExtractFunctionsOut`), чтобы весь сценарий шёл в mock-режиме
без ключа. S15 заменяет эти файлы реальными ответами (`LLM_MODE=live LLM_RECORD_MOCKS=1`),
код при этом не меняется. Правила:
- вводная без собственного действия («Работники БВА имеют право:», «… следующие функции:») и
  общие фразы без действия — не функция;
- текст — слова пункта; перечень глаголов через запятую («…, представляет …») делится на
  атомарные функции; подпункт-фрагмент дополняется словами родителя («… в части …»,
  «проверка …»); длинный пункт обрезается по границе предложения или запятой;
- исполнитель — из ближайшей вводной/родителя (как `functions.inherited_executor`);
- модальность — словари парсера S04 (`clause_modality`), запрет во вводной действует всегда;
- категория — раздел 2.3 → task, 2.4 и прочее в разделах 2 и 4 → function, раздел 5 →
  right/duty (запрет — duty, «несет ответственность» — responsibility);
- пункты контекста — родители из `section_path`, переданные во входе.

Запуск: `cd backend && LLM_MODE=mock uv run python -m app.mocks.extract_functions.draft_fixtures`
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.functions import (
    assign_clauses,
    build_payload,
    executor_phrase,
    function_clauses,
    inherited_executor,
    mock_fixture_path,
)
from app.llm import LLM
from app.parse.docx import clause_modality, parse_docx
from app.schemas import Clause, Document
from app.units import detect_units

DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "case11"
DOC_BEFORE = "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx"
DOC_AFTER = "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx"
OUT_DIR = Path(__file__).resolve().parent

TEXT_MAX = 220
# Общие фразы без действия: не функции.
NOT_FUNCTIONS = (
    "Задачи внутреннего аудита определяются",
    "Общий порядок и методика проведения внутреннего аудита",
    "Содействие Совету директоров Общества и исполнительным органам",
)
_MARKERS_RE = re.compile(
    r"\b(?:не\s+имеют?\s+права|имеют?\s+право|не\s+вправе|вправе|обязаны?|обязан)\b",
    re.IGNORECASE,
)
# Запятая перед новым сказуемым того же лица («…, представляет …», «…, представлять …»).
_VERB_SPLIT_RE = re.compile(r",\s+(?=(?:[а-яё]+(?:ет|ит|ют|ят)|[а-яё]+(?:ать|ять|еть|ить))\s)")
_NOT_VERBS = {
    "отчет",
    "учет",
    "расчет",
    "совет",
    "бюджет",
    "предмет",
    "комитет",
    "объект",
    "аспект",
    "проект",
    "аудит",
    "кредит",
    "лимит",
    "визит",
    "интернет",
    "может",
    "могут",
    "следует",
}
_TAIL_RE = re.compile(r",?\s*(?:в том числе|включая проверку|в части|по вопросам|обеспечивая)$")
_SENTENCE_RE = re.compile(r"\.\s+(?=[А-ЯЁ])")


def _lead_only(clause: Clause) -> bool:
    """Пункт только вводит перечень и своего действия не содержит."""
    text = clause.text.strip()
    if not text.endswith(":"):
        return False
    if "следующ" in text.lower():
        return True
    rest = text.rstrip(":")
    executor = executor_phrase(text)
    if executor:
        rest = rest.replace(executor, " ").replace(executor[0].lower() + executor[1:], " ")
    rest = re.sub(r"\((?:далее)[^)]*\)", " ", rest, flags=re.IGNORECASE)
    rest = _MARKERS_RE.sub(" ", rest)
    rest = re.sub(r"^\s*(?:Для\s+выполнения.*?,)", " ", rest)
    words = [w for w in re.findall(r"[А-Яа-яЁё]+", rest) if len(w) > 2]
    return len(words) <= 2 or bool(re.search(r"обеспечивает\s*$", rest.strip()))


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().rstrip(";:.,").strip()


def _shorten(text: str) -> str:
    first = _SENTENCE_RE.split(text, maxsplit=1)[0]
    if len(first.split()) >= 4:
        text = first
    text = _TAIL_RE.sub("", text).strip()
    if len(text) <= TEXT_MAX:
        return text
    sentence = text.find(". ")
    if 40 <= sentence <= TEXT_MAX:
        return text[:sentence]
    comma = text.rfind(", ", 0, TEXT_MAX)
    if comma >= 40:
        return text[:comma]
    return text[: text.rfind(" ", 0, TEXT_MAX)]


def _split(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    for m in _VERB_SPLIT_RE.finditer(text):
        word = re.match(r"[а-яё]+", text[m.end() :])
        if word is None or word.group(0) in _NOT_VERBS:
            continue
        parts.append(text[start : m.start()])
        start = m.end()
    parts.append(text[start:])
    merged: list[str] = []
    for part in (p.strip() for p in parts):
        if merged and len(part.split()) < 3:
            merged[-1] += ", " + part
        elif part:
            merged.append(part)
    return merged


def _compose(clause: Clause, parent: Clause | None) -> str:
    """Подпункт-фрагмент дополняется словами родителя; самостоятельный пункт — как есть."""
    text = _clean(clause.text)
    executor = executor_phrase(clause.text) if clause.text.rstrip().endswith(":") else None
    if executor and text.startswith(executor):
        # «Главный аудитор обязан обеспечить …, а также имеет право:» → «обязан обеспечить …»
        text = text[len(executor) :].split(", а также", 1)[0].strip()
    if parent is None or not text or text[0].isupper():
        return text
    head = _clean(parent.text)
    if head.endswith("в части"):
        return head.rsplit(", ", 1)[-1] + " " + text
    if head.endswith("включая проверку"):
        return "проверка " + text
    if head.endswith("по вопросам") and text.split()[0][-1] in "ия":
        return "содействие по вопросам " + text
    return text


def _category(clause: Clause, modality: str, text: str) -> str:
    number = clause.number or ""
    if number.startswith("2.3"):
        return "task"
    if number.startswith(("2.", "4.")):
        return "function"
    if "несет ответственность" in text.lower() or "несут ответственность" in text.lower():
        return "responsibility"
    return "right" if modality == "right" else "duty"


def draft_answer(doc: Document, payload: dict[str, Any]) -> dict[str, Any]:
    by_number = {c.number: c for c in doc.clauses if c.number}
    passed = {entry["number"] for entry in payload["clauses"]}
    functions: list[dict[str, Any]] = []
    for entry in payload["clauses"]:
        clause = by_number[entry["number"]]
        if _lead_only(clause) or clause.text.startswith(NOT_FUNCTIONS):
            continue
        parents = [
            by_number[n]
            for el in reversed(clause.section_path)
            if (n := (re.match(r"^(\d+(?:\.\d+)+)\.", el) or [None, None])[1]) in by_number
        ]
        parent = parents[0] if parents else None
        text = _compose(clause, parent)
        pieces = [_shorten(p) for p in _split(text)] if text else []
        executor = inherited_executor(clause, by_number)
        if executor is None and clause.text.rstrip().endswith(":"):
            executor = executor_phrase(clause.text)
        if executor is None and executor_phrase(clause.text) in ("БВА", "Общество"):
            executor = executor_phrase(clause.text)
        context = [p.number for p in parents if p.number in passed]
        for piece in pieces:
            lead_in = None if piece.startswith("обязан") else clause.lead_in
            modality = clause_modality(piece, lead_in)
            if clause.modality == "prohibition":
                modality = "prohibition"
            functions.append(
                {
                    "text": piece,
                    "category": _category(clause, modality, piece),
                    "executor": executor,
                    "modality": modality,
                    "clause_number": entry["number"],
                    "context_clause_numbers": context,
                }
            )
    return {"functions": functions}


def main() -> None:
    llm = LLM()
    before = parse_docx(DATA_DIR / DOC_BEFORE, "before")
    after = parse_docx(DATA_DIR / DOC_AFTER, "after")
    result = detect_units(before, after, llm)
    for stale in OUT_DIR.glob("*.json"):
        stale.unlink()
    for doc, units in ((before, result.units_before), (after, result.units_after)):
        by_id = {u.id: u for u in units}
        groups = assign_clauses(doc, units)
        calls = [(by_id.get(uid) if uid else None, cl) for uid, cl in groups.items()]
        calls.append((None, function_clauses(doc)))  # весь документ: extract_functions(doc, None)
        for unit, clauses in calls:
            payload = build_payload(doc, unit, clauses)
            answer = draft_answer(doc, payload)
            path = mock_fixture_path(payload)
            path.write_text(json.dumps(answer, ensure_ascii=False, indent=2) + "\n", "utf-8")
            name = unit.name if unit else "(весь документ)"
            print(f"{doc.version} {name}: {len(answer['functions'])} → {path.name}")


if __name__ == "__main__":
    main()
