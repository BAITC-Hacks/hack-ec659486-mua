"""P3 «Функции и запреты» (spec §2 P3, §3, §5 extract_functions).

Порядок шага:
1. Выбор пунктов (код). Область — разделы о функциях: заголовок раздела говорит о задачах,
   функциях, правах, обязанностях, полномочиях или о работе в ДЗО (в тестовом комплекте —
   разделы 2, 4 и 5); таких разделов нет — все нумерованные пункты. Пункты без номера,
   заголовки разделов и пустые пункты модели не передаются. Каждый пункт идёт с контекстом
   из `Clause`: `section_path`, `lead_in`, `modality`.
2. Привязка к подразделению (код). `extract_all` делит пункты области между подразделениями
   версии: владелец пункта — подразделение, названное исполнителем в ближайшей вводной или
   родительском пункте («Директор ДНМ …:», «…, БВА:»); если вводная называет несколько
   подразделений («Директоры … ДИТААД и ДОА:»), а сам пункт — одно из них, берётся оно, иначе —
   их общий родитель. Нет исполнителя в контексте — подразделение из текста пункта (если оно
   одно), иначе корневое (БВА). Один пункт — одному подразделению: иначе одна и та же функция
   попала бы в дубли. `extract_functions(doc, unit, llm)` без готового списка берёт пункты
   области, где названо подразделение, плюс его `unit.sources`.
3. `extract_functions` (LLM, strict-схема) на пунктах одного подразделения. Ответ проверяется
   кодом: `clause_number` не из переданного списка или пустой `text` — запись отброшена;
   чужие номера в `context_clause_numbers` выброшены; к ним код добавляет родительские пункты
   из `section_path`. Запрет, который видит код (вводная или текст пункта: «не имеет права»,
   «не вправе», «запрещается», «не допускается»), побеждает модальность модели. Пустой
   `executor` заполняется кодом из ближайшей вводной/родителя («Главный аудитор:»).
4. Записи с `modality == "prohibition"` — не функции, а ограничения: второй список результата.
   Сигнатура `lib_normalize.signature` — только кандидат для поиска (S10), не решение.

Mock-режим: `mocks/extract_functions/<hash>.json`, `hash = sha256(json.dumps(payload,
ensure_ascii=False, sort_keys=True))[:16]`; нет файла → `LLMError` с именем ожидаемого файла.
Live-режим: ответ кэшируется в памяти по тому же хэшу (повторный вызов без LLM); с
`LLM_RECORD_MOCKS=1` ответ модели сохраняется как фикстура (S15 заменяет ручные фикстуры).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.llm import LLM, MOCKS_DIR, LLMError, strict_schema, validate_output
from app.parse.docx import lead_in_modality
from app.prebuilt.lib_normalize import signature
from app.schemas import Clause, Document, Function, FunctionCategory, Modality, Source, Unit
from app.units import abbreviation_of, normalize_name, payload_hash

logger = logging.getLogger(__name__)

NAME = "extract_functions"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
RECORD_ENV = "LLM_RECORD_MOCKS"
EXECUTOR_MAX_WORDS = 12

# Кэш живых ответов по хэшу входа: повторный прогон того же документа не тратит токены.
_LIVE_CACHE: dict[str, dict[str, Any]] = {}


# --- Схема ответа LLM (spec §5; strict: все поля обязательны, executor — null, если нет) ----


class ExtractedFunction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    category: FunctionCategory
    executor: str | None
    modality: Modality
    clause_number: str
    context_clause_numbers: list[str]


class ExtractFunctionsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    functions: list[ExtractedFunction]


# --- Область: разделы о функциях ----------------------------------------------------------

_FUNCTION_SECTION_RE = re.compile(
    r"функци|задач|обязанност|полномочи|(?<![а-яё])прав[ао](?![а-яё])|(?<![а-яё])дзо(?![а-яё])"
    r"|дочерн",
    re.IGNORECASE,
)
_HAS_LETTER_RE = re.compile(r"[A-Za-zА-Яа-яЁё]")
_LEADING_NUMBER_RE = re.compile(r"^\s*(\d+(?:\.\d+)*(?:\.[а-яё])?)\.?(?:\s|$)", re.IGNORECASE)


def _is_heading(clause: Clause) -> bool:
    """Заголовок раздела: «5.» с текстом, равным названию раздела."""
    return bool(clause.number) and clause.section == f"{clause.number}. {clause.text}"


def _passable(clause: Clause) -> bool:
    return (
        clause.number is not None
        and not _is_heading(clause)
        and bool(_HAS_LETTER_RE.search(clause.text))
    )


def function_clauses(doc: Document) -> list[Clause]:
    """Пункты области: разделы о задачах/функциях/правах/обязанностях; нет таких — все."""
    passable = [c for c in doc.clauses if _passable(c)]
    picked = [c for c in passable if c.section and _FUNCTION_SECTION_RE.search(c.section)]
    return picked or passable


# --- Упоминания подразделений и исполнитель ------------------------------------------------

_WORD_RE = re.compile(r"[a-zа-яё0-9]+(?:-[a-zа-яё0-9]+)*")


def _stems(text: str) -> list[str]:
    """Грубые основы слов (первые 5 букв): «департамента» и «департамент» совпадают."""
    return [w[:5] for w in _WORD_RE.findall(text.lower().replace("ё", "е"))]


def _abbr_re(abbr: str) -> re.Pattern[str]:
    return re.compile(r"(?<![А-Яа-яЁёA-Za-z0-9])" + re.escape(abbr) + r"(?![А-Яа-яЁёA-Za-z0-9])")


class _UnitIndex:
    """Поиск упоминаний подразделений версии в тексте: по основам названия и аббревиатуре."""

    def __init__(self, units: list[Unit]) -> None:
        self.units = units
        self.by_id = {u.id: u for u in units}
        self._stems = {u.id: _stems(normalize_name(u.name)) for u in units}
        self._abbr = {
            u.id: _abbr_re(abbr) for u in units if (abbr := abbreviation_of(u.name)) is not None
        }

    def mentioned(self, text: str | None) -> list[Unit]:
        """Подразделения, названные в тексте, в порядке первого упоминания."""
        if not text:
            return []
        words = _stems(text)
        found: list[tuple[int, Unit]] = []
        for unit in self.units:
            positions: list[int] = []
            stems = self._stems[unit.id]
            if stems:
                n = len(stems)
                positions += [i for i in range(len(words) - n + 1) if words[i : i + n] == stems]
            pattern = self._abbr.get(unit.id)
            if pattern is not None and (m := pattern.search(text)) is not None:
                positions.append(len(_stems(text[: m.start()])))
            if positions:
                found.append((min(positions), unit))
        found.sort(key=lambda item: item[0])
        return [unit for _, unit in found]

    def ancestors(self, unit: Unit) -> list[str]:
        chain: list[str] = []
        current: Unit | None = unit
        while current is not None and current.id not in chain:
            chain.append(current.id)
            current = self.by_id.get(current.parent) if current.parent else None
        return chain

    def common_parent(self, units: list[Unit]) -> Unit | None:
        chains = [self.ancestors(u) for u in units]
        for uid in chains[0]:
            if all(uid in chain for chain in chains[1:]):
                return self.by_id[uid]
        return None


_ROLE_START_RE = re.compile(
    r"^(?:главн\w*\s+аудитор\w*|директор\w*|руководител\w*|начальник\w*|заместител\w*"
    r"|менеджер\w*|аудитор\w*|куратор\w*|работник\w*|сотрудник\w*|специалист\w*"
    r"|департамент\w*|отдел\w*|управлени\w*|служб\w*|блок\w*|сектор\w*|групп\w*|центр\w*"
    r"|обществ\w*|президент\w*|правлени\w*|совет\w*\s+директоров|комитет\w*"
    r"|(?-i:[А-ЯЁ]{2,})(?![а-яё]))",
    re.IGNORECASE,
)
# Где кончается исполнитель во вводной: модальный маркер, глагол-действие, двоеточие.
_EXECUTOR_STOP_RE = re.compile(
    r"\s+(?:не\s+вправе|не\s+имеют?\s+права|имеют?\s+право|вправе|обязан\w*|долж[енны]+"
    r"|осуществля\w*|обеспечива\w*|несет|несут|несёт|отвечает|отвечают"
    r"|[а-яё]+(?:ет|ют|ит|ят|ется|ются|ится|ятся))(?![а-яё])"
    r"|\s*[:;]",
)
_FURTHER_RE = re.compile(r"\s*\((?:далее|далее\s+по\s+тексту)[^)]*\)", re.IGNORECASE)


def executor_phrase(text: str | None) -> str | None:
    """Исполнитель из вводной или пункта-родителя: «5.3. Директор ДНМ:» → «Директор ДНМ».

    Кандидаты по порядку: хвост вводной перед двоеточием после последней запятой/точки
    («…, БВА:» → «БВА», «…, Общество обеспечивает:» → «Общество»), начало фразы и его хвост
    после последней запятой («…в ДЗО, Главный аудитор или уполномоченное им лицо
    осуществляет …» → «Главный аудитор или уполномоченное им лицо»). Каждый кандидат режется
    на первом модальном маркере, глаголе или двоеточии и должен начинаться с должности или
    подразделения; иначе None.
    """
    if not text:
        return None
    body = _FURTHER_RE.sub("", _strip_number(text.strip())).strip()
    candidates: list[str] = []
    if body.endswith(":"):
        candidates.append(re.split(r"[,.;]", body.rstrip(":"))[-1])
    head = _cut(body)
    candidates.append(head)
    if "," in head:
        candidates.append(head.rsplit(",", 1)[-1])
    for candidate in candidates:
        phrase = re.sub(r"\s+", " ", _cut(candidate)).strip(" .,;:–—-")
        if not phrase or len(phrase.split()) > EXECUTOR_MAX_WORDS:
            continue
        if _ROLE_START_RE.match(phrase):
            return phrase[0].upper() + phrase[1:]
    return None


def _cut(text: str) -> str:
    stop = _EXECUTOR_STOP_RE.search(text)
    return text[: stop.start()] if stop else text


def _strip_number(text: str) -> str:
    return _LEADING_NUMBER_RE.sub("", text, count=1)


def _leading_number(text: str) -> str | None:
    m = _LEADING_NUMBER_RE.match(text)
    return m.group(1) if m else None


def _parents(clause: Clause, by_number: dict[str, Clause]) -> list[Clause]:
    """Пункты-родители из `section_path`, ближайший первым (только существующие в документе)."""
    found: list[Clause] = []
    for element in reversed(clause.section_path):
        number = _leading_number(element)
        parent = by_number.get(number) if number else None
        if parent is not None and parent.id != clause.id and not _is_heading(parent):
            found.append(parent)
    return found


def _executor_contexts(clause: Clause, by_number: dict[str, Clause]) -> list[str]:
    """Тексты, где может стоять исполнитель: родители (ближайший первым), затем вся вводная."""
    texts = [p.text for p in _parents(clause, by_number)]
    if clause.lead_in:
        texts.append(clause.lead_in)
    return texts


def inherited_executor(clause: Clause, by_number: dict[str, Clause]) -> str | None:
    """Исполнитель, унаследованный от ближайшей вводной или родительского пункта."""
    for text in _executor_contexts(clause, by_number):
        executor = executor_phrase(text)
        if executor is not None:
            return executor
    return None


def _owner(clause: Clause, index: _UnitIndex, by_number: dict[str, Clause]) -> Unit | None:
    """Подразделение-владелец пункта (см. docstring модуля, шаг 2); None — не определено."""
    own = index.mentioned(clause.text)
    for text in _executor_contexts(clause, by_number):
        executor = executor_phrase(text)
        if executor is None:
            continue
        # Первый найденный исполнитель решает: должность без подразделения («Главный
        # аудитор:») — корень, а не подразделение, случайно упомянутое в тексте пункта.
        found = index.mentioned(executor)
        if not found:
            return None
        narrowed = [u for u in own if u in found]
        if len(narrowed) == 1:
            return narrowed[0]
        if len(found) == 1:
            return found[0]
        return index.common_parent(found)
    if len(own) == 1:
        return own[0]
    if own:
        return index.common_parent(own)
    return None


def _root(units: list[Unit]) -> Unit | None:
    roots = [u for u in units if not u.parent]
    return roots[0] if len(roots) == 1 else None


def assign_clauses(doc: Document, units: list[Unit]) -> dict[str | None, list[Clause]]:
    """Пункты области → подразделение-владелец (Unit.id); None — владельца нет и корня нет."""
    index = _UnitIndex(units)
    by_number = {c.number: c for c in doc.clauses if c.number}
    root = _root(units)
    groups: dict[str | None, list[Clause]] = {}
    for clause in function_clauses(doc):
        owner = _owner(clause, index, by_number) if units else None
        owner = owner or root
        groups.setdefault(owner.id if owner else None, []).append(clause)
    return groups


def select_clauses(doc: Document, unit: Unit | None) -> list[Clause]:
    """Пункты для одного подразделения: область, где оно названо, плюс его `unit.sources`."""
    scope = function_clauses(doc)
    if unit is None:
        return scope
    index = _UnitIndex([unit])
    source_ids = {s.clause_id for s in unit.sources if s.doc_id == doc.id}
    return [
        c
        for c in scope
        if c.id in source_ids
        or any(index.mentioned(t) for t in (c.text, c.lead_in, *c.section_path))
    ]


# --- Вход модели и вызов LLM --------------------------------------------------------------


def _refs(clauses: list[Clause]) -> dict[str, Clause]:
    """Адрес пункта для модели: печатный номер; повтор номера — стабильный id блока."""
    refs: dict[str, Clause] = {}
    for clause in sorted(clauses, key=lambda c: c.index):
        ref = clause.number or clause.id
        refs[ref if ref not in refs else clause.id] = clause
    return refs


def build_payload(doc: Document, unit: Unit | None, clauses: list[Clause]) -> dict[str, Any]:
    """Вход `extract_functions`; пункты по `index` — хэш стабилен при любом порядке на входе."""
    return {
        "version": doc.version,
        "unit": unit.name if unit is not None else "",
        "clauses": [
            {
                "number": ref,
                "text": clause.text,
                "section_path": list(clause.section_path),
                "lead_in": clause.lead_in or "",
                "modality": clause.modality,
            }
            for ref, clause in _refs(clauses).items()
        ],
    }


def mock_fixture_path(payload: dict[str, Any]) -> Path:
    return MOCKS_DIR / NAME / f"{payload_hash(payload)}.json"


def _load_prompt() -> str:
    return (PROMPTS_DIR / f"{NAME}.md").read_text(encoding="utf-8")


def _call_llm(llm: LLM, payload: dict[str, Any]) -> ExtractFunctionsOut:
    key = payload_hash(payload)
    path = mock_fixture_path(payload)
    if llm.mode == "mock":
        if not path.is_file():
            raise LLMError(
                f"нет mock-фикстуры для '{NAME}': ожидался файл mocks/{NAME}/{path.name}. "
                "Для своих документов нужен ключ OpenAI в .env (LLM_MODE=live)."
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise LLMError(f"mock-фикстура {path} содержит невалидный JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise LLMError(f"mock-фикстура {path} должна содержать JSON-объект")
        logger.debug("functions mock: %s/%s", NAME, path.name)
    elif key in _LIVE_CACHE:
        data = _LIVE_CACHE[key]
        logger.debug("functions: ответ %s из кэша", key)
    else:
        data = llm.complete_json(
            name=NAME,
            system=_load_prompt(),
            user=json.dumps(payload, ensure_ascii=False),
            schema=strict_schema(ExtractFunctionsOut),
        )
        _LIVE_CACHE[key] = data
        if os.environ.get(RECORD_ENV) == "1":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
            logger.info("functions: ответ сохранён как фикстура %s", path.name)
    return validate_output(ExtractFunctionsOut, data, NAME)


def clear_cache() -> None:
    """Сбросить кэш живых ответов (тесты, смена модели)."""
    _LIVE_CACHE.clear()


# --- Ответ модели → Function ---------------------------------------------------------------


def code_sees_prohibition(clause: Clause) -> bool:
    """Запрет по вводной или собственному тексту пункта (словари и правила парсера S04)."""
    return clause.modality == "prohibition" or lead_in_modality(clause.lead_in) == "prohibition"


def _own_executor(clause: Clause) -> str | None:
    """Пункт-вводная сам называет исполнителя: «5.2. Главный аудитор обязан …, имеет право:»."""
    return executor_phrase(clause.text) if clause.text.rstrip().endswith(":") else None


def _function_id(doc: Document, clause_number: str, text: str) -> str:
    return hashlib.sha1((doc.id + clause_number + text).encode("utf-8")).hexdigest()[:12]


def _source(doc: Document, clause: Clause) -> Source:
    return Source(
        doc_id=doc.id,
        doc_name=doc.name,
        version=doc.version,
        clause_id=clause.id,
        clause_number=clause.number,
        quote=clause.text,
    )


def _convert(
    doc: Document,
    unit: Unit | None,
    refs: dict[str, Clause],
    out: ExtractFunctionsOut,
) -> tuple[list[Function], list[Function]]:
    by_number = {c.number: c for c in doc.clauses if c.number}
    functions: list[Function] = []
    constraints: list[Function] = []
    seen: set[str] = set()
    for item in out.functions:
        text = item.text.strip()
        ref = item.clause_number.strip()
        clause = refs.get(ref)
        if not text:
            logger.warning("extract_functions: запись без текста отброшена (пункт %s)", ref)
            continue
        if clause is None:
            logger.warning(
                "extract_functions: «%s» отброшена — пункта %r нет среди переданных", text, ref
            )
            continue
        foreign = [n for n in item.context_clause_numbers if n not in refs]
        if foreign:
            logger.warning("extract_functions: «%s» — чужие пункты контекста: %s", text, foreign)
        context = [refs[n].number or n for n in item.context_clause_numbers if n in refs]
        context += [p.number for p in _parents(clause, by_number) if p.number]
        context = [n for n in dict.fromkeys(context) if n != clause.number]

        modality: Modality = item.modality
        if modality != "prohibition" and code_sees_prohibition(clause):
            logger.info("extract_functions: пункт %s — запрет по вводной/тексту", clause.number)
            modality = "prohibition"
        executor = (
            (item.executor or "").strip()
            or inherited_executor(clause, by_number)
            or _own_executor(clause)
        )

        fid = _function_id(doc, clause.number or clause.id, text)
        if fid in seen:
            continue
        seen.add(fid)
        function = Function(
            id=fid,
            unit_id=unit.id if unit is not None else None,
            text=text,
            category=item.category,
            modality=modality,
            executor=executor,
            action=None,
            object=None,
            signature=signature(text),
            context_clause_numbers=context,
            sources=[_source(doc, clause)],
        )
        (constraints if modality == "prohibition" else functions).append(function)
    return functions, constraints


# --- Точки входа шага P3 -------------------------------------------------------------------


def extract_functions(
    doc: Document,
    unit: Unit | None,
    llm: LLM,
    *,
    clauses: list[Clause] | None = None,
) -> tuple[list[Function], list[Function]]:
    """(функции, ограничения) одного подразделения; `unit=None` — область всего документа.

    `clauses` — готовый список пунктов (так вызывает `extract_all`); без него пункты
    выбирает `select_clauses`.
    """
    source = clauses if clauses is not None else select_clauses(doc, unit)
    picked = [c for c in source if _passable(c)]
    if not picked:
        return [], []
    payload = build_payload(doc, unit, picked)
    out = _call_llm(llm, payload)
    return _convert(doc, unit, _refs(picked), out)


def extract_all(
    doc: Document, units: list[Unit], llm: LLM
) -> tuple[list[Function], list[Function]]:
    """(функции, ограничения) документа: по одному вызову на подразделение-владельца пунктов.

    Подразделений нет — один вызов на всю область документа (`unit_id = None`).
    """
    own_units = [u for u in units if u.version == doc.version]
    if not own_units:
        return extract_functions(doc, None, llm)
    groups = assign_clauses(doc, own_units)
    functions: list[Function] = []
    constraints: list[Function] = []
    by_id = {u.id: u for u in own_units}
    for unit_id, clauses in groups.items():
        unit = by_id.get(unit_id) if unit_id else None
        f, c = extract_functions(doc, unit, llm, clauses=clauses)
        functions += f
        constraints += c
    return functions, constraints


def _main(argv: list[str]) -> int:
    """`uv run python -m app.functions до.docx после.docx` — функции на реальных документах."""
    if len(argv) != 2:
        print("использование: python -m app.functions <до.docx> <после.docx>", file=sys.stderr)
        return 2
    from app.parse.docx import parse_docx
    from app.units import detect_units

    llm = LLM()
    docs = [parse_docx(argv[0], "before"), parse_docx(argv[1], "after")]
    try:
        result = detect_units(docs[0], docs[1], llm)
        for doc, units in zip(docs, (result.units_before, result.units_after), strict=True):
            functions, constraints = extract_all(doc, units, llm)
            names = {u.id: u.name for u in units}
            print(f"[{doc.version}] функций {len(functions)}, ограничений {len(constraints)}")
            for fn in functions + constraints:
                src = fn.sources[0].clause_number
                unit_name = names.get(fn.unit_id or "", "—")
                print(f"  {src:9} {fn.modality:11} {unit_name[:30]:30} {fn.executor} :: {fn.text}")
    except LLMError as exc:
        print(f"LLMError: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(_main(sys.argv[1:]))
