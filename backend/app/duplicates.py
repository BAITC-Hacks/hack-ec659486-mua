"""P5 «Дубли функций» (spec §2 P4a/P4b, §5 verify_duplicates) для одной версии документа.

Порядок:
1. Кандидаты — пары функций РАЗНЫХ подразделений (исполнителей) одной версии. Источник: готовые
   `candidate_pairs` (их считает S08 на шаге `candidates` через `app.candidates`), иначе ленивый
   `app.candidates.find_duplicate_candidates`, а если модуля нет — запасной генератор по равенству
   сигнатуры. Похожесть и сигнатура — только кандидат, не решение.
2. Код отсекает то, что дублем быть не может: запреты (`modality = prohibition`), шаблонные
   формулировки (`TEMPLATE_PHRASES`), участие/содействие/соисполнительство на любой стороне,
   пары внутри одного подразделения.
3. Решает LLM `verify_duplicates` — по одному вызову на пару. Ответ `is_duplicate = true`
   принимается, только если все признаки (`same_action`, `same_object`, `both_executors`)
   истинны; иначе ответ невалиден и пара остаётся «требует проверки».

Контракт `Duplicate` (schemas.py закрыт) не содержит полей `verification` и `sources`:
источники — `function_a.sources` и `function_b.sources`, вид проверки записан в `note`
(«Проверка: llm» или «Проверка: lexical»).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.llm import LLM, LLMError
from app.prebuilt.lib_normalize import object_head, signature
from app.rules import (
    STOP_WORDS,
    allowed_numbers,
    call_llm,
    clean_clause_refs,
    function_payload,
    is_participation,
    iter_owned,
    norm,
    stem,
)
from app.schemas import Duplicate, Function


class VerifyDuplicatesOut(BaseModel):
    """Ответ `verify_duplicates` (spec §5). Поля и strict-схема — как в `app.llm_schemas` (S13),
    но своя модель без валидатора согласованности: противоречивый ответ (is_duplicate=true без
    всех признаков) должен дойти до `_answer_problem` и стать «требует проверки: ответ проверки
    противоречив», а не «нет ответа проверки» из-за ошибки схемы."""

    model_config = ConfigDict(extra="forbid")

    is_duplicate: bool
    same_action: bool
    same_object: bool
    both_executors: bool
    verification_note: str


logger = logging.getLogger(__name__)

LLM_NAME = "verify_duplicates"
MAX_DUPLICATE_CALLS = 200  # вызовов verify_duplicates на одну версию документа
MAX_CANDIDATES_PER_FUNCTION = 5

# Шаблонные формулировки: функция, в которой они есть, не сравнивается (spec §2 P4a).
TEMPLATE_PHRASES: tuple[str, ...] = (
    "иные функции",
    "другие функции",
    "прочие функции",
    "иные обязанности",
    "другие обязанности",
    "иные полномочия",
    "другие полномочия",
    "иные задачи",
    "прочих поручений",
    "прочие поручения",
    "иных поручений",
    "иные поручения",
    "поручения руководства",
    "поручений руководства",
    "поручению руководства",
    "согласно законодательству",
    "в соответствии с законодательством",
    "в пределах компетенции",
    "в пределах своей компетенции",
    "в рамках компетенции",
)
# Формулировка, делающая всю функцию шаблонной («прочих поручений Главного аудитора»).
_GENERIC_RE = re.compile(
    r"\b(ин\w+|друг\w+|проч\w+)\s+(функци|обязанност|полномочи|поручени|задани)\w*"
    r"|\bпоручени\w*\s+руководств"
)
MIN_CONTENT_WORDS = 3  # после снятия шаблонов должно остаться хотя бы столько значимых слов

PairsSource = Callable[[list[Function]], Any]


def is_template(text: str) -> bool:
    """Шаблонная функция: «иные функции», «прочих поручений …», «поручения руководства», или
    после снятия шаблонных оборотов («согласно законодательству», «в пределах компетенции»)
    почти не осталось содержания."""
    t = norm(text)
    if _GENERIC_RE.search(t):
        return True
    for phrase in TEMPLATE_PHRASES:
        t = t.replace(phrase, " ")
    words = [w for w in re.findall(r"[а-яa-z0-9-]+", t) if len(w) > 3 and w not in STOP_WORDS]
    return len(words) < MIN_CONTENT_WORDS


def _eligible(fn: Function) -> bool:
    """Может ли функция вообще быть стороной дубля."""
    if fn.modality == "prohibition":
        return False  # запрет — ограничение, а не функция
    if is_template(fn.text):
        return False
    return not is_participation(fn.text)


def _similarity(a: Function, b: Function) -> float:
    """Лексическая оценка пары 0..1 (Жаккар по основам слов) — только для показа."""

    def stems(fn: Function) -> set[str]:
        words = re.findall(r"[а-яa-z0-9-]+", norm(fn.text))
        return {stem(w) for w in words if len(w) > 2 and w not in STOP_WORDS}

    sa, sb = stems(a), stems(b)
    if not sa or not sb:
        return 0.0
    return round(len(sa & sb) / len(sa | sb), 3)


def _signature_of(fn: Function) -> str:
    return fn.signature or signature(fn.text)


def signature_candidates(
    functions_by_unit: dict[str, list[Function]],
) -> list[tuple[Function, Function, float]]:
    """Запасной генератор: равенство сигнатуры у функций разных владельцев. Сигнатура без
    объекта («ПРОЧЕЕ|», «КОНТРОЛИРОВАТЬ|») слишком общая и кандидатом не считается."""
    by_sig: dict[str, list[tuple[str, Function]]] = {}
    for owner, fn in iter_owned(functions_by_unit):
        sig = _signature_of(fn)
        obj = sig.partition("|")[2]
        if not obj.strip() or not object_head(fn.text):
            continue
        by_sig.setdefault(sig, []).append((owner, fn))
    pairs: list[tuple[Function, Function, float]] = []
    for group in by_sig.values():
        for i, (owner_a, a) in enumerate(group):
            for owner_b, b in group[i + 1 :]:
                if owner_a != owner_b:
                    pairs.append((a, b, _similarity(a, b)))
    return pairs


def _load_candidates_module() -> PairsSource | None:
    try:
        from app.candidates import find_duplicate_candidates  # type: ignore[import-not-found]
    except ImportError:
        return None
    return find_duplicate_candidates


def _as_pair(
    item: Any, by_id: dict[str, Function]
) -> tuple[Function, Function, float | None] | None:
    """Пара из результата `app.candidates` в любом разумном виде: (a, b, score), (a, b),
    dict/объект с a/b или function_a/function_b и score/similarity; функции или их id."""
    if isinstance(item, (tuple, list)) and len(item) >= 2:
        a, b = item[0], item[1]
        score = item[2] if len(item) > 2 else None
    else:
        get = item.get if isinstance(item, dict) else lambda k, d=None: getattr(item, k, d)
        a = get("a") or get("function_a") or get("left")
        b = get("b") or get("function_b") or get("right")
        score = get("score", None)
        if score is None:
            score = get("similarity", None)
    a = by_id.get(a) if isinstance(a, str) else a
    b = by_id.get(b) if isinstance(b, str) else b
    if not isinstance(a, Function) or not isinstance(b, Function):
        return None
    try:
        value = float(score) if score is not None else None
    except (TypeError, ValueError):
        value = None
    return a, b, value


def _prepare_pairs(
    raw_pairs: Iterable[Any], functions_by_unit: dict[str, list[Function]]
) -> list[tuple[Function, Function, float]]:
    """Фильтр кандидатов: известные функции, разные владельцы, без запретов, шаблонов и
    участия, без повторов, не больше MAX_CANDIDATES_PER_FUNCTION на функцию."""
    owners: dict[str, str] = {}
    by_id: dict[str, Function] = {}
    for owner, fn in iter_owned(functions_by_unit):
        owners[fn.id] = owner
        by_id[fn.id] = fn
    seen: set[frozenset[str]] = set()
    per_function: dict[str, int] = {}
    prepared: list[tuple[Function, Function, float]] = []
    for item in raw_pairs or []:
        pair = _as_pair(item, by_id)
        if pair is None:
            continue
        a, b, score = pair
        if a.id not in owners or b.id not in owners or a.id == b.id:
            continue
        if owners[a.id] == owners[b.id]:
            continue  # внутри одного подразделения не сравниваем
        if not (_eligible(a) and _eligible(b)):
            continue
        key = frozenset((a.id, b.id))
        if key in seen:
            continue
        if (
            per_function.get(a.id, 0) >= MAX_CANDIDATES_PER_FUNCTION
            or per_function.get(b.id, 0) >= MAX_CANDIDATES_PER_FUNCTION
        ):
            continue
        seen.add(key)
        per_function[a.id] = per_function.get(a.id, 0) + 1
        per_function[b.id] = per_function.get(b.id, 0) + 1
        similarity = score if score is not None and 0.0 <= score <= 1.0 else _similarity(a, b)
        prepared.append((a, b, similarity))
    return prepared


def _collect_candidates(
    functions_by_unit: dict[str, list[Function]],
    candidate_pairs: Sequence[Any] | None,
) -> tuple[list[Any], str]:
    if candidate_pairs is not None:
        return list(candidate_pairs), "кандидаты шага candidates"
    finder = _load_candidates_module()
    if finder is None:
        logger.warning("app.candidates недоступен, кандидаты только по сигнатуре")
        return signature_candidates(functions_by_unit), "равенство сигнатуры"
    flat = [fn for _, fn in iter_owned(functions_by_unit)]
    try:
        return list(finder(flat) or []), "гибридный поиск app.candidates"
    except Exception as exc:  # чужой модуль не должен ронять шаг
        logger.warning(
            "app.candidates.find_duplicate_candidates упал (%s), кандидаты только по сигнатуре",
            type(exc).__name__,
        )
        return signature_candidates(functions_by_unit), "равенство сигнатуры"


def verify_payload(
    a: Function, b: Function, unit_names: dict[str, str] | None = None
) -> dict[str, Any]:
    names = unit_names or {}
    return {
        "a": function_payload(a, names.get(a.unit_id or "")),
        "b": function_payload(b, names.get(b.unit_id or "")),
    }


def _check_answer(out: Any) -> str | None:
    """Причина невалидности ответа или None. is_duplicate=true требует всех трёх признаков."""
    if out.is_duplicate:
        false_flags = [
            name
            for name in ("same_action", "same_object", "both_executors")
            if not getattr(out, name)
        ]
        if false_flags:
            return "ответ проверки противоречив: is_duplicate=true при " + ", ".join(
                f"{name}=false" for name in false_flags
            )
    return None


def _duplicate(
    a: Function, b: Function, similarity: float, verified: bool, note: str, verification_note: str
) -> Duplicate:
    return Duplicate(
        id="",
        function_a=a,
        function_b=b,
        similarity=max(0.0, min(1.0, similarity)),
        note=note,
        verified=verified,
        verification_note=verification_note,
    )


def find_duplicates(
    functions_by_unit: dict[str, list[Function]],
    llm: LLM,
    candidate_pairs: list[tuple[Function, Function, float]] | None = None,
    *,
    unit_names: dict[str, str] | None = None,
) -> list[Duplicate]:
    """Дубли функций между подразделениями одной версии. Подтверждённые LLM — первыми
    (`verified=True`), затем кандидаты без ответа проверки (`verified=False`, «требует
    проверки: <причина>»). Пары, которые LLM признала не дублями, не возвращаются."""
    if not functions_by_unit or not any(functions_by_unit.values()):
        return []
    raw, origin = _collect_candidates(functions_by_unit, candidate_pairs)
    pairs = _prepare_pairs(raw, functions_by_unit)
    if not pairs:
        return []

    confirmed: list[Duplicate] = []
    unverified: list[Duplicate] = []
    calls = 0
    for a, b, similarity in pairs:
        candidate_note = f"Кандидат: {origin}, оценка {similarity:.2f}."
        if calls >= MAX_DUPLICATE_CALLS:
            reason = f"превышен лимит проверок ({MAX_DUPLICATE_CALLS} на версию)"
        else:
            calls += 1
            reason = None
            try:
                out = call_llm(llm, LLM_NAME, verify_payload(a, b, unit_names), VerifyDuplicatesOut)
                reason = _check_answer(out)
            except LLMError as exc:
                reason = f"нет ответа проверки ({exc})"
            except Exception as exc:  # процесс не падает из-за одной пары
                logger.exception("verify_duplicates: сбой на паре %s / %s", a.id, b.id)
                reason = f"сбой проверки ({type(exc).__name__})"
            if reason is None:
                if not out.is_duplicate:
                    continue  # LLM: не дубль — пары нет
                note_text, removed = clean_clause_refs(
                    out.verification_note.strip(), allowed_numbers((a, b))
                )
                if removed:
                    logger.warning("verify_duplicates: удалены чужие номера пунктов %s", removed)
                confirmed.append(
                    _duplicate(
                        a,
                        b,
                        similarity,
                        True,
                        f"Проверка: llm ({LLM_NAME}). {candidate_note}",
                        note_text or "одно действие над одним объектом у двух исполнителей",
                    )
                )
                continue
        unverified.append(
            _duplicate(
                a,
                b,
                similarity,
                False,
                f"Проверка: lexical — не подтверждено LLM. {candidate_note}",
                f"требует проверки: {reason}",
            )
        )

    result = confirmed + unverified
    return [dup.model_copy(update={"id": f"dup-{i}"}) for i, dup in enumerate(result, start=1)]
