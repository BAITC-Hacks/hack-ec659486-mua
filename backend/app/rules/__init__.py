"""Общие узкие правила P5 (дубли и конфликты интересов, spec §2 P5): разбор функции на
действие и объект, исключения, LLM-вызов с фикстурой по хэшу входа, чистка номеров пунктов.

Всё здесь детерминированно и без морфологии: ведущее действие ищется в начале текста функции
(после вспомогательных «обеспечивает», «осуществляет», «организует», «проводит»), объект —
слова после действия до первого разделителя, без хвоста-ссылки («в соответствии с …»).
Похожесть объектов — только условие, решение о находке принимают правила и проверка LLM.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.llm import LLM, MOCKS_DIR, LLMError, strict_schema, validate_output
from app.prebuilt.lib_normalize import object_head
from app.schemas import Function

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
RECORD_ENV = "LLM_RECORD_MOCKS"  # live + LLM_RECORD_MOCKS=1 — ответ сохраняется фикстурой

# --- нормализация и токены -------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[а-яa-z0-9]+(?:-[а-яa-z0-9]+)*|,")
_PARENS_RE = re.compile(r"\([^()]*\)")
_ENDING_RE = re.compile(
    r"(ами|ями|ов|ев|ей|ий|ый|ой|ая|яя|ое|ее|ые|ие|ых|их|ым|им|ую|юю|ого|его|ому|ему|"
    r"ах|ях|ам|ям|ом|ем|а|я|о|е|и|ы|у|ю|ь|й)$"
)

# Слова, которые не несут объекта: предлоги, связки, общие названия организации.
STOP_WORDS = frozenset(
    "в во и или либо на по с со для из от до при об о а также том числе т ч к ко за под над "
    "через между без после его ее их её всех всего всей всем своей своих свой своего "
    "общества общество обществе обществом компании бва имени рамках целях пределах "
    "соответствии соответствующих настоящим настоящего положением положения "
    "установленном установленные установленных предусмотренном предусмотренных "
    "необходимых необходимые необходимой иных иные других другие прочих прочие "
    "своевременно своевременную полноту надлежащее ответственности зоне".split()
)

AUX_TOKEN_RE = re.compile(r"^(обеспеч|осуществл|организ|координир|провод|проведен|реализ|выполн)")
PREPOSITIONS = frozenset("по при в во для без после до с со о об на за под через от из к".split())
DOC_NOUN_RE = re.compile(
    r"^(акт|план|программ|отчет|график|заключени|протокол|результат|материал|журнал|реестр)"
)

STRONG_RE = re.compile(
    r"^(утвержд|утверд|подпис|контрол|проверя|проверк|провер(?:ит|ить|ять)|аудир)"
)
WEAK_RE = re.compile(r"^(согласов|визир)")
INIT_RE = re.compile(r"^(иницииру|инициир|вносит|вносят|вносить|внесени|предлага)")
APPROVE_RE = re.compile(r"^(утвержд|утверд)")
EXEC_RE = re.compile(
    r"^(разраб|созда|формир|составл|подготов|готов|оформл|внедр|вед[еу]т|вест|веден|учит|"
    r"учет|регистр|актуализ|начисл|расч|исполн|эксплуат|обслуж|заполн|выда|изда|закуп|"
    r"приобрет|заключ|оплач|оплат|выплач|выплат|перечисл|инвентар|архивир|консолид|"
    r"сопровожд|обраб|принима|принят)"
)
REFERENCE_RE = re.compile(r"^(руководств|соблюд|примен|использ|ссыла|следу|изуча|знаком)")
# Прочие действия: распознаются как действие, но ни исполнением, ни контролем не считаются.
OTHER_ACTION_RE = re.compile(
    r"^(анализ|представл|направл|запрашива|взаимодейств|информир|консульт|обуча|монитор|"
    r"рассматр|оцен|выявл|определ|планир|участ|содейств)"
)
_ACTION_RE = re.compile(
    "|".join(
        rx.pattern for rx in (STRONG_RE, WEAK_RE, INIT_RE, EXEC_RE, REFERENCE_RE, OTHER_ACTION_RE)
    )
)
_ADJ_END_RE = re.compile(
    r"(ый|ий|ой|ая|яя|ое|ее|ые|ие|ых|их|ым|им|ыми|ими|ую|юю|ого|его|ому|ему|ом|ем)$"
)
_VERBAL_NOUN_RE = re.compile(r"(ние|тие|нием|тием)$")
_REFERENCE_TAIL = ("в соответствии с", "согласно", "на основании", "руководствуясь", "в порядке")

# --- исключения (spec §2 P5) ----------------------------------------------------------------

PARTICIPATION_RE = re.compile(r"\b(участ\w*|содейств\w*|соисполн\w*|оказ\w*\s+помощ\w*|помога\w*)")
ORG_AND_CONTROL_RE = re.compile(r"\bорганиз\w*\s+и\s+(?:осуществлени\w+\s+)?контрол\w*")
SEND_FOR_APPROVAL_RE = re.compile(
    r"\bна\s+(?:предварительн\w+\s+)?(?:согласовани|утверждени|подписани|рассмотрени)\w*"
)
OWN_PLANNING_RE = re.compile(
    r"(годов\w*\s+план\w*\s+(?:работ\w*\s+)?(?:внутренн\w+\s+)?"
    r"(?:аудит|бва|проверок|работ|деятельност|подразделени|департамент|отдел)"
    r"|план\w*\s+работ"
    r"|план\w*\s+(?:внутренн\w+\s+)?аудит"
    r"|отчет\w*\s+(?:о|об)\s+(?:своей\s+)?(?:работ|деятельност|итогах\s+"
    r"(?:работы|выполнения\s+план|деятельност))"
    r"|отчет\w*\s+(?:о\s+)?выполнени\w*\s+план)"
)
FOREIGN_RE = re.compile(
    r"(подрядчик|поставщик|контрагент|сторонн\w+\s+организац|других\s+подразделени|"
    r"иных\s+подразделени|подразделени\w+\s+общества|руководител\w+\s+(?:общества|объект)|"
    r"объект\w*\s+аудит|третьих\s+лиц|внешн\w+\s+аудитор|независим\w+\s+аудитор|\bдзо\b|"
    r"подконтрольн|исполнител\w+\s+договор)"
)
DOCNAME_CONTROL_RE = re.compile(
    r"\b(акт|план|программ|отчет|график|заключени|протокол|результат|журнал|реестр)\w*\s+"
    r"(?:[а-я]+\s+){0,2}?(проверк|контрол|аудит|ревизи|мониторинг)\w*"
)


def norm(text: str | None) -> str:
    """Нижний регистр, ё→е, одинарные пробелы."""
    return re.sub(r"\s+", " ", (text or "").lower().replace("ё", "е")).strip()


def stem(word: str) -> str:
    """Грубая основа слова: одно окончание долой, не длиннее 5 букв («закупок» = «закупки»)."""
    base = _ENDING_RE.sub("", word) if len(word) > 3 else word
    return (base or word)[:5]


def _is_action(tokens: list[str], i: int) -> bool:
    tok = tokens[i]
    if tok != "аудит":  # «аудит ИТ-систем» — действие, «аудитор» — нет
        if not _ACTION_RE.match(tok):
            return False
        if _ADJ_END_RE.search(tok) and not _VERBAL_NOUN_RE.search(tok):
            return False  # «контрольные процедуры», «утвержденным планом»
    prev = tokens[i - 1] if i > 0 else ""
    if prev in PREPOSITIONS:
        return False  # «по согласованию с …», «на утверждение»
    if prev and DOC_NOUN_RE.match(prev):
        return False  # «акт проверки», «план контроля»
    return True


@dataclass(frozen=True)
class Action:
    """Ведущее действие функции и её объект."""

    aux: tuple[str, ...]  # снятые вспомогательные глаголы
    verbs: tuple[str, ...]  # ведущие действия («составляет», «утверждает»)
    object_words: tuple[str, ...]  # слова объекта без стоп-слов
    object_text: str  # объект как фраза (для регулярных правил)

    @property
    def object_stems(self) -> tuple[str, ...]:
        return tuple(stem(w) for w in self.object_words)

    @property
    def verb_stems(self) -> frozenset[str]:
        return frozenset(v[:5] for v in self.verbs)

    @property
    def head_stem(self) -> str:
        """Главное слово объекта: первое не-прилагательное («внутренних аудиторских
        проверок» → «прове», «годовой план аудита» → «план»)."""
        for word in self.object_words:
            if not _ADJ_END_RE.search(word) or _VERBAL_NOUN_RE.search(word):
                return stem(word)
        return stem(self.object_words[0]) if self.object_words else ""

    @property
    def organizes_only(self) -> bool:
        """«Организует/координирует X» без собственного действия — управленческая функция."""
        return (
            not self.verbs
            and bool(self.aux)
            and all(re.match(r"^(организ|координир)", a) for a in self.aux)
        )


def parse_action(text: str, executor: str | None = None) -> Action:
    """Действие и объект по началу текста функции (исполнитель в начале снимается)."""
    t = _PARENS_RE.sub(" ", norm(text))
    t = re.sub(r"^(?:\d+(?:\.\d+)*\.?|[а-я][.)])\s+", "", t)  # номер пункта в начале
    ex = norm(executor)
    if ex and t.startswith(ex):
        t = t[len(ex) :]
    segment = re.split(r"[;:]", t, maxsplit=1)[0]
    tokens = _TOKEN_RE.findall(segment)

    aux: list[str] = []
    i = 0
    while i < len(tokens) and len(aux) < 3:
        tok = tokens[i]
        if tok in ("и", ","):
            i += 1
        elif AUX_TOKEN_RE.match(tok):
            aux.append(tok)
            i += 1
        elif tok.startswith("принима") and i + 1 < len(tokens) and tokens[i + 1] == "участие":
            aux.append("принимает участие")
            i += 2
        else:
            break

    verbs: list[str] = []
    start = i
    for j in range(i, min(i + 6, len(tokens))):
        if tokens[j] == ",":
            break
        if _is_action(tokens, j):
            verbs.append(tokens[j])
            start = j + 1
            while (
                start + 1 < len(tokens)
                and tokens[start] in ("и", "или", ",")
                and _is_action(tokens, start + 1)
            ):
                verbs.append(tokens[start + 1])
                start += 2
            break

    obj: list[str] = []
    rest = tokens[start:]
    for k, tok in enumerate(rest):
        if tok == ",":
            break
        nxt = rest[k + 1] if k + 1 < len(rest) else ""
        if tok in ("и", "или") and (AUX_TOKEN_RE.match(nxt) or _is_action(rest, k + 1)):
            break  # «проводят проверки и обеспечивают …» — дальше другое действие
        obj.append(tok)
    object_text = " ".join(obj)
    for marker in _REFERENCE_TAIL:
        pos = f" {object_text} ".find(f" {marker} ")
        if pos != -1:
            object_text = object_text[:pos].strip()
    words = tuple(
        w for w in object_text.split() if len(w) > 2 and w not in STOP_WORDS and w != ","
    )[:6]
    return Action(tuple(aux), tuple(verbs), words, object_text)


def action_of(fn: Function) -> Action:
    return parse_action(fn.text, fn.executor)


def control_strength(text: str, executor: str | None = None) -> str | None:
    """Сила контроля ведущего действия: strong — утверждает/подписывает/контролирует/проверяет/
    аудирует; weak — только согласовывает (не находка); иначе None."""
    verbs = parse_action(text, executor).verbs
    if any(STRONG_RE.match(v) or v == "аудит" for v in verbs):
        return "strong"
    if any(WEAK_RE.match(v) for v in verbs):
        return "weak"
    return None


def object_overlap(f1: Function, f2: Function) -> float:
    """Перекрытие объектов двух функций 0..1: совпадение `object_head` или доля общих основ
    слов объекта (к меньшему объекту, если его главное слово есть у другого; иначе Жаккар)."""
    return action_overlap(action_of(f1), action_of(f2))


def action_overlap(a1: Action, a2: Action) -> float:
    """Перекрытие объектов двух разобранных действий 0..1 (см. `object_overlap`)."""
    head1, head2 = object_head(a1.object_text), object_head(a2.object_text)
    if head1 and head1 == head2:
        return 1.0
    set1, set2 = set(a1.object_stems), set(a2.object_stems)
    common = set1 & set2
    if not common:
        return 0.0
    short, other = (a1, set2) if len(set1) <= len(set2) else (a2, set1)
    if len(set(short.object_stems)) >= 2 and short.head_stem in other:
        return len(common) / min(len(set1), len(set2))
    return len(common) / len(set1 | set2)


def is_participation(text: str) -> bool:
    return bool(PARTICIPATION_RE.search(norm(text)))


def exclusion_reason(functions: Sequence[Function], control: Function | None = None) -> str | None:
    """Причина исключения пары/функции из конфликтов или None. `control` — контролирующая
    сторона (если есть), остальные — исполняющие."""
    texts = [norm(fn.text) for fn in functions]
    if any(PARTICIPATION_RE.search(t) for t in texts):
        return "участие/содействие/соисполнитель: сторона сама не исполняет и не контролирует"
    if any(ORG_AND_CONTROL_RE.search(t) for t in texts):
        return "управленческий оборот «организация и контроль»"
    if control is not None and any(
        fn is not control and action_of(fn).organizes_only for fn in functions
    ):
        return "управленческий оборот «организация и контроль»: организует и контролирует"
    if any(SEND_FOR_APPROVAL_RE.search(t) for t in texts):
        return "направляет на согласование/утверждение: решение принимает другой"
    objects = [action_of(fn).object_text for fn in functions]
    if any(OWN_PLANNING_RE.search(o) for o in objects):
        return "собственное планирование и отчётность подразделения, не операционная деятельность"
    if any(FOREIGN_RE.search(t) for t in texts):
        return "надзор за чужим исполнением (подрядчик, поставщик, другие подразделения)"
    if control is not None and control_strength(control.text, control.executor) != "strong":
        if any(DOCNAME_CONTROL_RE.search(t) for t in texts):
            return "контрольное слово — часть названия документа, а не действие"
    if any(action_of(fn).verbs and REFERENCE_RE.match(action_of(fn).verbs[0]) for fn in functions):
        return "ссылается на документ, а не производит его"
    return None


# --- функции для LLM и проверка номеров пунктов ------------------------------------------------


def clause_number(fn: Function) -> str | None:
    return fn.sources[0].clause_number if fn.sources else None


def lead_in_of(fn: Function) -> str | None:
    """Вводная фраза: цитата дополнительного источника, оканчивающаяся двоеточием."""
    for src in fn.sources[1:]:
        if src.quote.rstrip().endswith(":"):
            return src.quote.strip()
    return None


def function_payload(fn: Function, unit_label: str | None) -> dict[str, Any]:
    return {
        "id": fn.id,
        "unit": unit_label or fn.unit_id or "",
        "executor": fn.executor or "",
        "modality": fn.modality,
        "text": fn.text,
        "clause_number": clause_number(fn) or "",
        "section_path": list(fn.context_clause_numbers),
        "lead_in": lead_in_of(fn) or "",
    }


def _num(value: str) -> str:
    return value.strip().rstrip(".").lower()


def allowed_numbers(functions: Iterable[Function]) -> set[str]:
    """Номера пунктов, на которые разрешено ссылаться: источники и контекст функций."""
    allowed: set[str] = set()
    for fn in functions:
        allowed.update(_num(s.clause_number) for s in fn.sources if s.clause_number)
        allowed.update(_num(n) for n in fn.context_clause_numbers if n)
    return allowed


_PREFIXED_REF_RE = re.compile(
    r"\b(?:пп?\.|пункт[а-я]*|подпункт[а-я]*)\s*([1-9]\d?(?:\.\d+)*(?:\.[а-я](?![а-я]))?)\.?",
    re.IGNORECASE,
)
_DOTTED_REF_RE = re.compile(r"(?<![\w.])([1-9]\d?(?:\.\d+)+(?:\.[а-я](?![а-я]))?)(?![\d])")


def clean_clause_refs(text: str, allowed: set[str]) -> tuple[str, list[str]]:
    """Удаляет из текста ссылки на пункты, которых нет среди переданных. Возвращает текст и
    удалённые номера (номер пункта от модели проверяется кодом, выдуманный не показывается)."""
    removed: list[str] = []

    def drop(match: re.Match[str]) -> str:
        number = _num(match.group(1))
        if number in allowed:
            return match.group(0)
        removed.append(number)
        return ""

    cleaned = _PREFIXED_REF_RE.sub(drop, text)
    cleaned = _DOTTED_REF_RE.sub(drop, cleaned)
    if removed:
        # пустые скобки и «(см. также )», оставшиеся без номера
        cleaned = re.sub(r"\((?:\s*(?:см|ср)\.?)?(?:\s*также)?\s*[,;и]?\s*\)", "", cleaned)
        cleaned = re.sub(r"\s+(?:и|,)\s*(?=[.;)])", "", cleaned)
        cleaned = re.sub(r"\s+([,.;:)])", r"\1", cleaned)
        cleaned = re.sub(r"\(\s+", "(", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned, removed


# --- LLM с фикстурой по хэшу входа -------------------------------------------------------------


def payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def mock_fixture_path(name: str, payload: dict[str, Any]) -> Path:
    return MOCKS_DIR / name / f"{payload_hash(payload)}.json"


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def call_llm(llm: LLM, name: str, payload: dict[str, Any], model: type[BaseModel]) -> Any:
    """Строгий JSON-ответ `name` на `payload`. Mock: `mocks/<name>/<hash>.json`, нет файла —
    `LLMError` с именем ожидаемого файла. Live + LLM_RECORD_MOCKS=1: ответ сохраняется туда же."""
    path = mock_fixture_path(name, payload)
    if llm.mode == "mock":
        if not path.is_file():
            raise LLMError(f"нет mock-фикстуры: ожидался файл mocks/{name}/{path.name}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise LLMError(f"mock-фикстура mocks/{name}/{path.name}: невалидный JSON") from exc
        if not isinstance(data, dict):
            raise LLMError(f"mock-фикстура mocks/{name}/{path.name} — не JSON-объект")
    else:
        data = llm.complete_json(
            name=name,
            system=load_prompt(name),
            user=json.dumps(payload, ensure_ascii=False),
            schema=strict_schema(model),
        )
        if os.environ.get(RECORD_ENV) == "1":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
            logger.info("%s: ответ сохранён как фикстура %s", name, path.name)
    return validate_output(model, data, name)


# --- владельцы функций ---------------------------------------------------------------------------


def owner_key(unit_key: str | None, fn: Function) -> str | None:
    """Кто исполняет: подразделение, а без него — исполнитель из текста; None — неизвестно."""
    if unit_key:
        return unit_key
    if fn.unit_id:
        return fn.unit_id
    if fn.executor:
        return f"executor:{norm(fn.executor)}"
    return None


def iter_owned(
    functions_by_unit: dict[str, list[Function]],
) -> Iterable[tuple[str, Function]]:
    """(владелец, функция) для всех функций входа; без владельца — пропуск."""
    for unit_key, functions in (functions_by_unit or {}).items():
        for fn in functions or []:
            key = owner_key(unit_key, fn)
            if key is not None:
                yield key, fn
