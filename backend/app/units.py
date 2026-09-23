"""P2 «Подразделения до/после» (spec §2 P2, §5 extract_units / match_units).

Порядок шага:
1. Словарные кандидаты (код): подразделения по словарю («департамент», «отдел», «управление»,
   «служба», «блок», «сектор», «группа», «центр», ДЗО, аббревиатуры в скобках) в тексте пункта,
   в его `section_path` и `lead_in`; должности-исполнители («Главный аудитор:», «Директор …:»)
   из вводных фраз и заголовков — отдельным списком, в подразделения не превращаются.
   Словарь — только кандидат, не решение.
2. `extract_units` (LLM, strict-схема) на разделе «Структура» каждой версии; номера пунктов из
   ответа проверяются по переданным пунктам, чужие отбрасываются. Подразделение из ответа
   обогащается пунктами словарного кандидата с тем же нормализованным названием/аббревиатурой.
3. Сопоставление: одинаковое нормализованное название или аббревиатура → kept без LLM;
   остаток (если он есть с обеих сторон) → `match_units` (LLM), пары проверяются по спискам.

Mock-режим: фикстуры по хэшу входа — `mocks/extract_units/<hash>.json`,
`mocks/match_units/<hash>.json`, `hash = sha256(json.dumps(payload, ensure_ascii=False,
sort_keys=True))[:16]`. Нет файла → `LLMError` с именем ожидаемого файла, без подмены.
Live-режим с `LLM_RECORD_MOCKS=1` сохраняет ответ модели в тот же файл (так S15 заменяет
ручные фикстуры реальными без правки кода).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.llm import LLM, MOCKS_DIR, LLMError, strict_schema, validate_output
from app.schemas import Clause, Document, Source, Unit, UnitChange, UnitChangeStatus

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
QUOTE_MAX_CHARS = 300  # цитата — дословный префикс текста пункта, без многоточия
MATCH_QUOTES_PER_UNIT = 4
RECORD_ENV = "LLM_RECORD_MOCKS"


# --- Схемы ответов LLM (strict: все поля обязательны, пустое значение — "") ----------------


class ExtractedUnit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    parent: str
    clause_numbers: list[str]


class ExtractUnitsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    units: list[ExtractedUnit]


class UnitPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    before: str
    after: str
    status: UnitChangeStatus
    note: str


class MatchUnitsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pairs: list[UnitPair]


# --- Нормализация названий -----------------------------------------------------------------

_KEYWORD_FORMS: dict[str, tuple[str, tuple[str, ...]]] = {
    # основа → (именительный падеж, допустимые окончания)
    "департамент": ("департамент", ("", "а", "у", "ом", "е", "ы", "ов", "ам", "ами", "ах")),
    "отдел": ("отдел", ("", "а", "у", "ом", "е", "ы", "ов", "ам", "ами", "ах")),
    "управлени": ("управление", ("е", "я", "ю", "ем", "и", "й", "ям", "ями", "ях")),
    "служб": ("служба", ("а", "ы", "е", "у", "ой", "", "ам", "ами", "ах")),
    "блок": ("блок", ("", "а", "у", "ом", "е", "и", "ов", "ам", "ами", "ах")),
    "сектор": ("сектор", ("", "а", "у", "ом", "е", "ы", "ов", "ам", "ами", "ах")),
    "групп": ("группа", ("а", "ы", "е", "у", "ой", "", "ам", "ами", "ах")),
    "центр": ("центр", ("", "а", "у", "ом", "е", "ы", "ов", "ам", "ами", "ах")),
}
_KEYWORD_RE = re.compile(
    r"(?<![А-Яа-яЁёA-Za-z])(" + "|".join(_KEYWORD_FORMS) + r")([а-яё]*)", re.IGNORECASE
)
# ДЗО — дочерние и зависимые общества: в словаре кандидатов по ТЗ, названия-фразы у них нет.
_DZO_ABBR = "ДЗО"
_ABBR_TOKEN = r"[А-ЯЁA-Z][А-ЯЁA-Z0-9\-]{1,11}"
_ABBR_AFTER_RE = re.compile(
    r"^(?:\s+(?:[Оо]бщества|[Кк]омпании))?\s*\((?:[Дд]алее\s*[-–—]?\s*)?(" + _ABBR_TOKEN + r")\)"
)
_ABBR_IN_NAME_RE = re.compile(r"\((?:[Дд]алее\s*[-–—]?\s*)?(" + _ABBR_TOKEN + r")\)")
_WORD_RE = re.compile(r"^(\s+)([А-Яа-яЁёA-Za-z0-9][А-Яа-яЁёA-Za-z0-9\-]*)")
_PHRASE_MAX_WORDS = 8
_STOP_WORDS = frozenset(
    "в во по с со на для от к ко о об при за из до а также или либо не как что который которая "
    "которые которого общества обществе обществом компании подчиняются подчиняется обязан "
    "обязаны имеет имеют вправе осуществляет осуществляют является являются состоит входит "
    "входящие несет несут это".split()
)
_ORG_SUFFIXES = ("общества", "компании")
# «управление рисками», «группа проверяет» — процесс и рабочая группа, а не подразделение:
# эти слова берём только с заглавной буквы («Управление персоналом», «Группа …»).
_CAPITALIZED_ONLY = frozenset({"управление", "группа"})
_VERB_RE = re.compile(r"^[а-яё]+(?:ет|ют|ит|ят|ется|ются|ится|ятся)$")

# Должность-исполнитель — только в именительном падеже: «Главному аудитору подчиняются …»
# говорит о подчинённых, а не об исполнителе.
_POSITION_RE = re.compile(
    r"^(главн(?:ый|ые)\s+аудитор(?:ы)?|директор(?:ы)?|руководител(?:ь|и)|менеджер(?:ы)?"
    r"|аудитор(?:ы)?|заместител(?:ь|и)|начальник(?:и)?|президент|специалист(?:ы)?|куратор(?:ы)?"
    r"|работник(?:и)?|сотрудник(?:и)?)(?![а-яё])",
    re.IGNORECASE,
)
_EXECUTOR_CUT_RE = re.compile(
    r"\s+(?:обязан\w*|имеет|имеют|вправе|не\s+вправе|не\s+имеет|не\s+имеют|осуществля\w*"
    r"|подчиня\w*|в\s+соответствии|состоит|несет|несут|отвечает|отвечают|должен|должны)\b.*$",
    re.IGNORECASE,
)
_NUMBER_PREFIX_RE = re.compile(r"^\s*(?:\d+(?:\.\d+)*\.?|[а-яё][.)])\s*", re.IGNORECASE)
_STRUCTURE_WORD_RE = re.compile(r"(?<![а-яё])структура(?![а-яё])", re.IGNORECASE)


def normalize_name(name: str) -> str:
    """Ключ сравнения названий: нижний регистр, без «(…)», ё→е, схлопнутые пробелы.

    Дополнительно: первое слово-тип подразделения приводится к именительному падежу
    («департамента» → «департамент»), хвостовое «Общества» отбрасывается.
    """
    text = name.lower().replace("ё", "е")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[«»\"“”„]", "", text)
    text = re.sub(r"\s+", " ", text).strip(" .,;:-–—")
    words = text.split(" ") if text else []
    if words:
        words[0] = _keyword_lemma(words[0]) or words[0]
    while len(words) > 1 and words[-1] in _ORG_SUFFIXES:
        words.pop()
    return " ".join(words)


def abbreviation_of(name: str) -> str | None:
    """Аббревиатура подразделения: «… (ДНМ)» → «ДНМ»; название-аббревиатура «БВА» → «БВА»."""
    found = _ABBR_IN_NAME_RE.findall(name)
    if found:
        return found[-1].upper()
    stripped = name.strip(" .,;:")
    if re.fullmatch(_ABBR_TOKEN, stripped) and stripped.upper() == stripped:
        return stripped
    return None


def _keyword_lemma(word: str) -> str | None:
    lower = word.lower().replace("ё", "е")
    for stem, (lemma, endings) in _KEYWORD_FORMS.items():
        if lower.startswith(stem) and lower[len(stem) :] in endings:
            return lemma
    return None


def _same_unit(key_a: str, abbr_a: str | None, key_b: str, abbr_b: str | None) -> bool:
    if key_a and key_a == key_b:
        return True
    return bool(abbr_a and abbr_b and abbr_a == abbr_b)


# --- Словарные кандидаты ------------------------------------------------------------------


@dataclass
class Candidate:
    """Кандидат в подразделение или должность: название + пункты, где он встречается.

    Пункты — сам пункт с упоминанием, пункты, у которых упоминание в `section_path`/`lead_in`,
    и вложенные по номеру пункты. Только кандидат: решение принимает `extract_units`.
    """

    name: str
    key: str
    kind: Literal["unit", "position"]
    abbr: str | None = None
    clause_ids: list[str] = field(default_factory=list)


@dataclass
class Position:
    """Должность-исполнитель («Главный аудитор», «Директор ДНМ») с пунктами-источниками.

    В `Unit` не превращается; S09 берёт её как `executor` функций.
    """

    name: str
    version: str
    clause_numbers: list[str]
    sources: list[Source]


@dataclass
class DocCandidates:
    units: list[Candidate]
    positions: list[Candidate]


def _context_texts(clause: Clause, by_number: dict[str, Clause]) -> list[str]:
    """Текст пункта + его контекст: элементы `section_path` (номер → текст пункта) и `lead_in`."""
    texts = [clause.text]
    for element in clause.section_path:
        parent = by_number.get(element.strip().rstrip("."))
        texts.append(parent.text if parent is not None else element)
    if clause.lead_in:
        texts.append(clause.lead_in)
    return texts


def _unit_phrases(text: str) -> list[tuple[str, str | None]]:
    """Словарные фразы-подразделения в тексте: [(название, аббревиатура|None)]."""
    found: list[tuple[str, str | None]] = []
    for match in _KEYWORD_RE.finditer(text):
        lemma = _keyword_lemma(match.group(0))
        if lemma is None or (lemma in _CAPITALIZED_ONLY and not match.group(0)[0].isupper()):
            continue
        words: list[str] = []
        pos = match.end()
        while len(words) < _PHRASE_MAX_WORDS:
            step = _WORD_RE.match(text[pos:])
            if step is None or "\n" in step.group(1):
                break
            word = step.group(2)
            lower = word.lower().replace("ё", "е")
            if (
                lower in _STOP_WORDS
                or _VERB_RE.match(word)
                or _POSITION_RE.match(word)
                or _keyword_lemma(word)
            ):
                break
            if lower == "и":
                after = _WORD_RE.match(text[pos + step.end() :])
                nxt = after.group(2) if after else ""
                if not nxt or nxt[0].isupper() or nxt.lower() in _STOP_WORDS:
                    break
            words.append(lower)
            pos += step.end()
        while words and words[-1] in ("и", *_ORG_SUFFIXES):
            words.pop()
        abbr_match = _ABBR_AFTER_RE.match(text[pos:])
        abbr = abbr_match.group(1).upper() if abbr_match else None
        if not words and abbr is None:
            continue
        found.append((" ".join([lemma, *words]), abbr))
    return found


def _executor_phrase(text: str) -> str | None:
    """Исполнитель из вводной или заголовка: «5.3. Директор направления …:» → «Директор …»."""
    phrase = _NUMBER_PREFIX_RE.sub("", text.strip(), count=1)
    phrase = re.sub(r"\((?:далее)[^)]*\)", " ", phrase, flags=re.IGNORECASE)
    phrase = re.split(r"[:,;]", phrase, maxsplit=1)[0]
    phrase = _EXECUTOR_CUT_RE.sub("", phrase)
    words = phrase.split()
    for i, word in enumerate(words[1:], start=1):  # «Куратор информирует …» → «Куратор»
        if _VERB_RE.match(word):
            phrase = " ".join(words[:i])
            break
    phrase = re.sub(r"\s+", " ", phrase).strip(" .,;–—-")
    if not phrase or len(phrase.split()) > 10 or not _POSITION_RE.match(phrase):
        return None
    return phrase[0].upper() + phrase[1:]


def _abbr_regex(abbr: str) -> re.Pattern[str]:
    return re.compile(r"(?<![А-Яа-яЁёA-Za-z0-9])" + re.escape(abbr) + r"(?![А-Яа-яЁёA-Za-z0-9])")


def find_candidates(doc: Document) -> DocCandidates:
    """Словарные кандидаты в подразделения и должности-исполнители одного документа."""
    by_number = {c.number: c for c in doc.clauses if c.number}
    units: dict[str, Candidate] = {}
    positions: dict[str, Candidate] = {}
    unit_hits: dict[str, set[str]] = {}
    position_hits: dict[str, set[str]] = {}

    contexts = {c.id: _context_texts(c, by_number) for c in doc.clauses}
    for clause in doc.clauses:
        for text in contexts[clause.id]:
            for name, abbr in _unit_phrases(text):
                key = normalize_name(name)
                cand = units.setdefault(key, Candidate(name=name, key=key, kind="unit"))
                if abbr and cand.abbr is None:
                    cand.abbr = abbr
                unit_hits.setdefault(key, set()).add(clause.id)
        # исполнитель: вводная фраза, заголовки-родители и сам пункт-вводная («…:»)
        heads = list(contexts[clause.id][1:])
        if clause.text.rstrip().endswith(":"):
            heads.append(clause.text)
        for head in heads:
            executor = _executor_phrase(head)
            if executor is None:
                continue
            key = normalize_name(executor)
            positions.setdefault(key, Candidate(name=executor, key=key, kind="position"))
            position_hits.setdefault(key, set()).add(clause.id)

    # аббревиатуры: «работники ДНМ», «БВА не имеет права:» → пункты кандидата с этой аббревиатурой
    abbr_owner = {c.abbr: c.key for c in units.values() if c.abbr}
    all_text = "\n".join(t for ts in contexts.values() for t in ts)
    if _DZO_ABBR not in abbr_owner and _abbr_regex(_DZO_ABBR).search(all_text):
        key = normalize_name(_DZO_ABBR)
        units[key] = Candidate(name=_DZO_ABBR, key=key, kind="unit", abbr=_DZO_ABBR)
        abbr_owner[_DZO_ABBR] = key
    for abbr, key in abbr_owner.items():
        pattern = _abbr_regex(abbr)
        for clause in doc.clauses:
            if any(pattern.search(t) for t in contexts[clause.id]):
                unit_hits.setdefault(key, set()).add(clause.id)

    def close(hits: set[str]) -> list[str]:
        """Пункты кандидата + вложенные по номеру, в порядке документа."""
        prefixes = [c.number + "." for c in doc.clauses if c.id in hits and c.number]
        return [
            c.id
            for c in doc.clauses
            if c.id in hits or (c.number and any(c.number.startswith(p) for p in prefixes))
        ]

    for key, cand in units.items():
        cand.clause_ids = close(unit_hits.get(key, set()))
    for key, cand in positions.items():
        cand.clause_ids = close(position_hits.get(key, set()))
    return DocCandidates(
        units=[c for c in units.values() if c.clause_ids],
        positions=[c for c in positions.values() if c.clause_ids],
    )


# --- Источники ----------------------------------------------------------------------------


def _source(doc: Document, clause: Clause) -> Source:
    return Source(
        doc_id=doc.id,
        doc_name=doc.name,
        version=doc.version,
        clause_id=clause.id,
        clause_number=clause.number,
        quote=clause.text[:QUOTE_MAX_CHARS].rstrip(),
    )


def _merge_sources(*groups: list[Source]) -> list[Source]:
    seen: set[tuple[str, str]] = set()
    merged: list[Source] = []
    for group in groups:
        for src in group:
            key = (src.doc_id, src.clause_id)
            if key not in seen:
                seen.add(key)
                merged.append(src)
    return merged


def _ref(clause: Clause) -> str:
    """Адрес пункта для LLM: печатный номер, у ненумерованных — стабильный id блока."""
    return clause.number or clause.id


# --- LLM с фикстурами по хэшу входа -------------------------------------------------------


def payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def mock_fixture_path(name: str, payload: dict[str, Any]) -> Path:
    return MOCKS_DIR / name / f"{payload_hash(payload)}.json"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _call_llm(llm: LLM, name: str, payload: dict[str, Any], model: type[BaseModel]) -> Any:
    path = mock_fixture_path(name, payload)
    if llm.mode == "mock":
        if not path.is_file():
            raise LLMError(
                f"нет mock-фикстуры для '{name}': ожидался файл mocks/{name}/{path.name}. "
                "Для своих документов нужен ключ OpenAI в .env (LLM_MODE=live)."
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise LLMError(f"mock-фикстура {path} содержит невалидный JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise LLMError(f"mock-фикстура {path} должна содержать JSON-объект")
        logger.debug("units mock: %s/%s", name, path.name)
    else:
        data = llm.complete_json(
            name=name,
            system=_load_prompt(name),
            user=json.dumps(payload, ensure_ascii=False),
            schema=strict_schema(model),
        )
        if os.environ.get(RECORD_ENV) == "1":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
            logger.info("units: ответ '%s' сохранён как фикстура %s", name, path.name)
    return validate_output(model, data, name)


# --- Шаг 2: extract_units ----------------------------------------------------------------


def structure_clauses(doc: Document) -> list[Clause]:
    """Раздел «Структура»: пункты, у которых в контексте есть элемент «3.…» или слово «Структура».

    Раздела нет — весь документ.
    """

    def in_structure(clause: Clause) -> bool:
        elements = [*clause.section_path, clause.section or ""]
        return any(el.strip().startswith("3.") or _STRUCTURE_WORD_RE.search(el) for el in elements)

    picked = [c for c in doc.clauses if in_structure(c)]
    return picked or list(doc.clauses)


def extract_units_payload(doc: Document) -> dict[str, Any]:
    clauses = sorted(structure_clauses(doc), key=lambda c: c.index)
    return {
        "version": doc.version,
        "clauses": [
            {
                "number": _ref(c),
                "section_path": list(c.section_path),
                "lead_in": c.lead_in or "",
                "text": c.text,
            }
            for c in clauses
        ],
    }


def extract_units(doc: Document, llm: LLM, candidates: DocCandidates | None = None) -> list[Unit]:
    """Подразделения одной версии: LLM на разделе «Структура» + пункты словарных кандидатов."""
    candidates = candidates if candidates is not None else find_candidates(doc)
    payload = extract_units_payload(doc)
    out: ExtractUnitsOut = _call_llm(llm, "extract_units", payload, ExtractUnitsOut)

    allowed = {entry["number"] for entry in payload["clauses"]}
    by_ref: dict[
        str, Clause
    ] = {}  # номер → пункт из переданного раздела (номера могут повторяться)
    for clause in sorted(structure_clauses(doc), key=lambda c: c.index):
        by_ref.setdefault(_ref(clause), clause)
    by_id = {c.id: c for c in doc.clauses}

    # (название, ключ, аббревиатура, родитель, пункты)
    accepted: list[tuple[str, str, str | None, str, list[Clause]]] = []
    for item in out.units:
        name = item.name.strip()
        if not name:
            logger.warning("extract_units: подразделение без названия отброшено")
            continue
        foreign = [n for n in item.clause_numbers if n not in allowed]
        if foreign:
            logger.warning(
                "extract_units: «%s» — чужие номера пунктов отброшены: %s", name, foreign
            )
        valid = list(dict.fromkeys(n for n in item.clause_numbers if n in allowed))
        if not valid:
            logger.warning("extract_units: «%s» отброшено — нет ни одного пункта-источника", name)
            continue
        if _POSITION_RE.match(name):
            logger.warning("extract_units: «%s» — должность, а не подразделение; отброшено", name)
            continue
        key, abbr = normalize_name(name), abbreviation_of(name)
        clauses = [by_ref[n] for n in valid]
        for i, (_, k, a, parent, known) in enumerate(accepted):
            if _same_unit(k, a, key, abbr):  # модель назвала одно подразделение дважды
                accepted[i] = (accepted[i][0], k, a or abbr, parent or item.parent.strip(), known)
                known.extend(c for c in clauses if c not in known)
                break
        else:
            accepted.append((name, key, abbr, item.parent.strip(), clauses))

    units: list[Unit] = []
    for i, (name, key, abbr, _, clauses) in enumerate(accepted):
        extra = [
            by_id[cid]
            for cand in candidates.units
            if _same_unit(cand.key, cand.abbr, key, abbr)
            for cid in cand.clause_ids
        ]
        extra.sort(key=lambda c: c.index)
        sources = _merge_sources(
            [_source(doc, c) for c in clauses], [_source(doc, c) for c in extra]
        )
        units.append(
            Unit(
                id=f"{doc.id}:unit:{i}",
                name=name,
                version=doc.version,
                parent=None,
                sources=sources,
            )
        )
    for unit, (_, _, _, parent, _) in zip(units, accepted, strict=True):
        if not parent:
            continue
        p_key, p_abbr = normalize_name(parent), abbreviation_of(parent)
        for other, (_, o_key, o_abbr, _, _) in zip(units, accepted, strict=True):
            if other is not unit and _same_unit(o_key, o_abbr, p_key, p_abbr):
                unit.parent = other.id
                break
    return units


def positions_of(doc: Document, candidates: DocCandidates) -> list[Position]:
    by_id = {c.id: c for c in doc.clauses}
    result: list[Position] = []
    for cand in candidates.positions:
        clauses = [by_id[cid] for cid in cand.clause_ids]
        result.append(
            Position(
                name=cand.name,
                version=doc.version,
                clause_numbers=[_ref(c) for c in clauses],
                sources=[_source(doc, c) for c in clauses],
            )
        )
    return result


# --- Шаг 3: сопоставление до↔после -------------------------------------------------------


def _change(
    idx: int, before: Unit | None, after: Unit | None, status: UnitChangeStatus, note: str
) -> UnitChange:
    return UnitChange(
        id=f"unit-change:{idx}",
        unit_before=before,
        unit_after=after,
        status=status,
        note=note,
        sources=_merge_sources(before.sources if before else [], after.sources if after else []),
    )


def match_units_payload(
    before: list[Unit],
    after: list[Unit],
    all_before: list[Unit] | None = None,
    all_after: list[Unit] | None = None,
) -> dict[str, Any]:
    """Вход `match_units`: несопоставленные подразделения; родитель — среди всех подразделений."""

    def describe(unit: Unit, units: list[Unit]) -> dict[str, Any]:
        parent = next((u.name for u in units if u.id == unit.parent), "")
        return {
            "name": unit.name,
            "parent": parent,
            "clauses": [
                {"number": s.clause_number or s.clause_id, "text": s.quote}
                for s in unit.sources[:MATCH_QUOTES_PER_UNIT]
            ],
        }

    return {
        "before": [describe(u, all_before or before) for u in before],
        "after": [describe(u, all_after or after) for u in after],
    }


def _pair_is_consistent(pair: UnitPair) -> bool:
    before, after = pair.before.strip(), pair.after.strip()
    if pair.status == "kept":
        return bool(before and after)
    if pair.status == "created":
        return not before and bool(after)
    if pair.status == "abolished":
        return bool(before) and not after
    # transformed: есть «до»; «после» может быть пустым при разделении/слиянии (см. note)
    return bool(before)


def match_units(
    units_before: list[Unit], units_after: list[Unit], llm: LLM, *, use_llm: bool = True
) -> list[UnitChange]:
    """Статусы подразделений: kept / transformed / created / abolished, с источниками обеих сторон.

    Одинаковое нормализованное название или аббревиатура → kept без LLM. Остаток с обеих
    сторон → `match_units` (LLM); `use_llm=False` — только детерминированно (Cut-if).
    """
    changes: list[UnitChange] = []
    used_after: set[str] = set()
    rest_before: list[Unit] = []
    for unit in units_before:
        key, abbr = normalize_name(unit.name), abbreviation_of(unit.name)
        twin = next(
            (
                a
                for a in units_after
                if a.id not in used_after
                and _same_unit(key, abbr, normalize_name(a.name), abbreviation_of(a.name))
            ),
            None,
        )
        if twin is None:
            rest_before.append(unit)
            continue
        used_after.add(twin.id)
        same_name = key == normalize_name(twin.name)
        note = (
            "Есть в обеих редакциях: совпадает название."
            if same_name
            else f"Есть в обеих редакциях: совпадает аббревиатура {abbr}."
        )
        changes.append(_change(len(changes), unit, twin, "kept", note))
    rest_after = [a for a in units_after if a.id not in used_after]

    paired_before: set[str] = set()
    paired_after: set[str] = set()
    if rest_before and rest_after and use_llm:
        payload = match_units_payload(rest_before, rest_after, units_before, units_after)
        out: MatchUnitsOut = _call_llm(llm, "match_units", payload, MatchUnitsOut)
        by_before = {u.name: u for u in rest_before}
        by_after = {u.name: u for u in rest_after}
        for pair in out.pairs:
            b_name, a_name = pair.before.strip(), pair.after.strip()
            before = by_before.get(b_name) if b_name else None
            after = by_after.get(a_name) if a_name else None
            if (b_name and before is None) or (a_name and after is None):
                logger.warning(
                    "match_units: пара отброшена — названия нет в списках: %r → %r",
                    b_name,
                    a_name,
                )
                continue
            if not _pair_is_consistent(pair):
                logger.warning(
                    "match_units: пара отброшена — статус %s не согласуется с %r → %r",
                    pair.status,
                    b_name,
                    a_name,
                )
                continue
            # kept/created/abolished — у подразделения одна запись; transformed допускает
            # разделение (одно «до» → несколько «после») и слияние (несколько «до» → одно «после»)
            repeat = (before is not None and before.id in paired_before) or (
                after is not None and after.id in paired_after
            )
            if repeat and pair.status != "transformed":
                logger.warning("match_units: повтор подразделения в паре %r → %r", b_name, a_name)
                continue
            note = pair.note.strip() or "Сопоставлено моделью."
            changes.append(_change(len(changes), before, after, pair.status, note))
            if before is not None:
                paired_before.add(before.id)
            if after is not None:
                paired_after.add(after.id)

    for unit in rest_before:
        if unit.id not in paired_before:
            changes.append(
                _change(
                    len(changes),
                    unit,
                    None,
                    "abolished",
                    "Нет в редакции «после»: подразделения с таким названием или аббревиатурой "
                    "не найдено.",
                )
            )
    for unit in rest_after:
        if unit.id not in paired_after:
            changes.append(
                _change(
                    len(changes),
                    None,
                    unit,
                    "created",
                    "Есть только в редакции «после»: в редакции «до» подразделения с таким "
                    "названием или аббревиатурой нет.",
                )
            )
    return changes


# --- Точка входа шага P2 ------------------------------------------------------------------


class UnitsResult(list[UnitChange]):
    """Результат `detect_units`: список `UnitChange` + подразделения и должности обеих версий.

    Ведёт себя как `list[UnitChange]` (контракт S08); должности (`positions_*`) S09 берёт
    как `executor` функций, подразделения (`units_*`) — для выбора пунктов по подразделению.
    """

    units_before: list[Unit]
    units_after: list[Unit]
    positions_before: list[Position]
    positions_after: list[Position]


def detect_units(
    doc_before: Document | list[Document],
    doc_after: Document | list[Document],
    llm: LLM | None = None,
    *,
    use_llm_match: bool = True,
) -> UnitsResult:
    """Какие подразделения сохранены / преобразованы / созданы / упразднены — с источниками.

    Версия — один документ или список (положение, ДИ, приказ): подразделения извлекаются из
    каждого документа и объединяются по названию или аббревиатуре, источники — из всех.
    """
    llm = llm or LLM()
    units_before, positions_before = _version_units(_as_documents(doc_before), llm)
    units_after, positions_after = _version_units(_as_documents(doc_after), llm)
    result = UnitsResult(match_units(units_before, units_after, llm, use_llm=use_llm_match))
    result.units_before = units_before
    result.units_after = units_after
    result.positions_before = positions_before
    result.positions_after = positions_after
    return result


def _as_documents(docs: Document | list[Document]) -> list[Document]:
    return [docs] if isinstance(docs, Document) else list(docs)


def _version_units(docs: list[Document], llm: LLM) -> tuple[list[Unit], list[Position]]:
    """Подразделения и должности одной версии по всем её документам, в порядке документов."""
    units: list[Unit] = []
    positions: list[Position] = []
    for doc in docs:
        candidates = find_candidates(doc)
        units = _merge_units(units, extract_units(doc, llm, candidates))
        positions.extend(positions_of(doc, candidates))
    return units, positions


def _merge_units(known: list[Unit], new: list[Unit]) -> list[Unit]:
    """Добавляет подразделения очередного документа версии к найденным в предыдущих.

    То же название или аббревиатура — одно подразделение: источники объединяются, ссылки
    `parent` на него переводятся на уже известный id. Внутри одного документа дубли уже
    схлопнуты `extract_units`, поэтому сравнение идёт только с `known`.
    """
    merged = list(known)
    alias: dict[str, str] = {}  # id из нового документа → id того же подразделения из прежних
    adopted: dict[int, str] = {}  # индекс в merged → parent, известный только новому документу
    for unit in new:
        key, abbr = normalize_name(unit.name), abbreviation_of(unit.name)
        twin = next(
            (
                i
                for i, other in enumerate(known)
                if _same_unit(normalize_name(other.name), abbreviation_of(other.name), key, abbr)
            ),
            None,
        )
        if twin is None:
            merged.append(unit)
            continue
        alias[unit.id] = merged[twin].id
        if merged[twin].parent is None and unit.parent:
            adopted[twin] = unit.parent
        merged[twin] = merged[twin].model_copy(
            update={"sources": _merge_sources(merged[twin].sources, unit.sources)}
        )
    for i, parent in adopted.items():
        parent = alias.get(parent, parent)
        if parent != merged[i].id:
            merged[i] = merged[i].model_copy(update={"parent": parent})
    for i in range(len(known), len(merged)):
        parent = merged[i].parent
        if parent is not None and parent in alias:
            merged[i] = merged[i].model_copy(update={"parent": alias[parent]})
    return merged


def _parse_docx(path: str, version: str) -> Document:
    """Разбор .docx парсером S04 (ленивый импорт: модуль может быть ещё не влит)."""
    try:
        from app.parse.docx import parse_docx  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "Парсер app.parse.docx (S04) ещё не влит в эту ветку — "
            "разбор .docx недоступен, detect_units принимает готовые Document."
        ) from exc
    return parse_docx(path, version)


def _main(argv: list[str]) -> int:
    """`uv run python -m app.units до.docx после.docx` — подразделения на реальных документах."""
    if len(argv) != 2:
        print("использование: python -m app.units <до.docx> <после.docx>", file=sys.stderr)
        return 2
    before, after = _parse_docx(argv[0], "before"), _parse_docx(argv[1], "after")
    for label, doc in (("до", before), ("после", after)):
        print(
            f"extract_units[{label}]: "
            f"{mock_fixture_path('extract_units', extract_units_payload(doc))}"
        )
    try:
        result = detect_units(before, after)
    except LLMError as exc:
        print(f"LLMError: {exc}", file=sys.stderr)
        return 1
    for change in result:
        b = change.unit_before.name if change.unit_before else "—"
        a = change.unit_after.name if change.unit_after else "—"
        print(f"{change.status:12} {b} → {a}  ({len(change.sources)} ист.) {change.note}")
    for pos in result.positions_before + result.positions_after:
        print(f"должность [{pos.version}] {pos.name}: {len(pos.clause_numbers)} п.")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(_main(sys.argv[1:]))
