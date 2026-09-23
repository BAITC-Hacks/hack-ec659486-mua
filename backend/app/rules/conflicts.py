"""P5 «Конфликты интересов» (spec §2 P5, §5 explain_conflict): узкие правила разделения
обязанностей для одной версии документа.

Находка возникает только у ОДНОГО подразделения (исполнителя) и только над ОДНИМ объектом:
- (a) исполняет (создаёт, проводит, ведёт учёт, эксплуатирует) и strong-контролирует объект
  («организует X» + «контролирует X» — управленческий оборот, не находка);
- (b) инициирует и утверждает объект (согласование — не утверждение);
- (c) внутренний аудит выполняет операционную функцию вне мандата (закупки, начисления, учёт,
  договоры, платёжные документы);
- (d) контроль возложен на контролируемого: объект strong-контроля — само подразделение;
- (e) функция прямо нарушает запрет документа («не имеют права …» из `constraints`).

Сила контроля: strong — «утверждает», «подписывает», «контролирует», «проверяет», «аудирует»;
weak — только «согласовывает», не находка. Исключения — `is_excluded`. Запреты
(`modality = prohibition`) — не функции: стороной (a)–(d) не бывают («не имеют права
инициировать и утверждать» — не «инициирует и утверждает»), но участвуют в (c) и (e).

Каждая находка проверяется LLM `explain_conflict`: `verified=true` — подтверждена;
`verified=false` или нет ответа — кандидат «требует проверки». Контракт `Conflict`
(schemas.py закрыт) не содержит поля `verification`; вид проверки — в `verification_note`.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.llm import LLM, LLMError
from app.prebuilt.lib_normalize import verb_class
from app.rules import (
    APPROVE_RE,
    EXEC_RE,
    INIT_RE,
    STRONG_RE,
    Action,
    action_of,
    action_overlap,
    allowed_numbers,
    call_llm,
    clause_number,
    clean_clause_refs,
    control_strength,
    exclusion_reason,
    function_payload,
    iter_owned,
    norm,
    object_overlap,
    stem,
)
from app.schemas import Conflict, Function, Severity, Source

try:  # S13 держит общие схемы LLM-вызовов; до его мержа — своя модель с теми же полями
    from app.llm_schemas import ExplainConflictOut  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - зависит от порядка мержа волны 3

    class ExplainConflictOut(BaseModel):  # type: ignore[no-redef]
        """Ответ `explain_conflict` (spec §5)."""

        model_config = ConfigDict(extra="forbid")

        explanation: str
        severity: Literal["low", "medium", "high"]
        verified: bool
        verification_note: str


logger = logging.getLogger(__name__)

LLM_NAME = "explain_conflict"
MAX_CONFLICT_CALLS = 100  # вызовов explain_conflict на одну версию документа
OBJECT_OVERLAP_MIN = 0.6  # «один и тот же объект»: доля общих основ слов объекта
EXEC_CLASSES = frozenset({"СОЗДАВАТЬ", "ОРГАНИЗОВЫВАТЬ", "ВЕСТИ_УЧЁТ", "ЭКСПЛУАТИРОВАТЬ"})

AUDIT_UNIT_RE = re.compile(r"аудит|ревиз|\bбва\b|\bсва\b")
FOREIGN_EXECUTOR_RE = re.compile(
    r"^(общество|президент|совет|комитет|правлени|акционер|руководител\w*\s+общества)"
)
MANDATE_CONSTRAINT_RE = re.compile(
    r"не\s+связанн\w+\s+с\s+деятельност\w+\s+(?:внутренн\w+\s+)?аудит"
)
SELF_OBJECT_RE = re.compile(
    r"\b(сво\w+|собственн\w+)\s+(деятельност|работ|функци|подразделени|департамент|отдел)"
)
_GENERIC_UNIT_WORDS = frozenset(
    "блок департамент департамента отдел отдела управление управления служба службы сектор "
    "сектора группа группы центр центра направление направления подразделение".split()
)


# --- признаки функций ---------------------------------------------------------------------------


def _strong_verbs(action: Action) -> list[str]:
    return [v for v in action.verbs if STRONG_RE.match(v) or v == "аудит"]


def is_execution(fn: Function) -> bool:
    """Функция исполняет объект: ведущее действие класса СОЗДАВАТЬ/ОРГАНИЗОВЫВАТЬ/ВЕСТИ_УЧЁТ/
    ЭКСПЛУАТИРОВАТЬ (по `verb_class`), либо «обеспечивает/проводит/организует X» без своего
    глагола (пара «организует X» + «контролирует X» потом исключается как управленческая)."""
    action = action_of(fn)
    if any(EXEC_RE.match(v) or verb_class(f"{v} объект") in EXEC_CLASSES for v in action.verbs):
        return True
    return bool(action.aux) and not action.verbs and bool(action.object_words)


def is_initiation(fn: Function) -> bool:
    return any(INIT_RE.match(v) for v in action_of(fn).verbs)


def is_approval(fn: Function) -> bool:
    return any(APPROVE_RE.match(v) for v in action_of(fn).verbs)


def operational_kind(fn: Function) -> str | None:
    """Операционная функция вне мандата аудита: закупки, начисления/платежи, учёт, договоры,
    платёжные и бухгалтерские документы. None — не операционная."""
    action = action_of(fn)
    obj = action.object_text
    text = norm(fn.text)
    for verb in action.verbs:
        if re.match(r"^(закуп|приобрет|тендер)", verb):
            return "закупки"
        if re.match(r"^(начисл|выплач|выплат|оплач|оплат|перечисл|платеж)", verb):
            return "начисления и платежи"
        if re.match(r"^учет", verb) or (re.match(r"^(вед|вест|учит)", verb) and "учет" in obj):
            return "ведение учёта"
        if verb.startswith("заключ") and "договор" in obj:
            return "заключение договоров"
        if re.match(r"^(подпис|визир|инициир|отража|формир|составл)", verb) and re.search(
            r"платеж|расчетн|бухгалтерск|проводк", obj
        ):
            return "платёжные и бухгалтерские документы"
    if re.search(r"бухгалтерск\w*\s+(операц|проводк|учет)", text) and "провод" in "".join(
        action.aux
    ):
        return "бухгалтерские операции"
    return None


# --- контекст подразделения ----------------------------------------------------------------


@dataclass
class UnitContext:
    owner: str
    unit_id: str | None
    name: str | None
    functions: list[Function]
    constraints: list[Function]
    abbreviations: set[str] = field(default_factory=set)

    @property
    def is_audit(self) -> bool:
        texts = [self.name or "", self.unit_id or ""] + [fn.executor or "" for fn in self.functions]
        return any(AUDIT_UNIT_RE.search(norm(t)) for t in texts)

    def refers_to_self(self, action: Action) -> bool:
        obj = action.object_text
        if SELF_OBJECT_RE.search(obj):
            return True
        tokens = set(obj.split())
        if self.abbreviations & tokens:
            return True
        if self.name:
            name_words = [
                w
                for w in re.findall(r"[а-я]+", norm(re.sub(r"\([^)]*\)", " ", self.name)))
                if len(w) > 3 and w not in _GENERIC_UNIT_WORDS
            ]
            name_stems = {stem(w) for w in name_words}
            if name_stems and name_stems <= set(action.object_stems):
                return True
        return False


_ABBR_RE = re.compile(r"\b[А-ЯЁ]{2,8}\b")


def _abbreviations(texts: Sequence[str | None]) -> set[str]:
    found: set[str] = set()
    for text in texts:
        found.update(norm(a) for a in _ABBR_RE.findall(text or ""))
    return found


def _constraint_applies(constraint: Function, ctx: UnitContext, owners: set[str]) -> bool:
    """Запрет без подразделения, запрет вышестоящего (не из списка подразделений) и запрет
    «работникам …» действуют на всех; иначе — только на своё подразделение."""
    unit = constraint.unit_id or ""
    if not unit or unit not in owners:
        return True
    if "работник" in norm(constraint.executor):
        return True
    return unit == ctx.owner


# --- правила -------------------------------------------------------------------------------


@dataclass
class RuleHit:
    functions: list[Function]
    detail: str


RuleCheck = Callable[[UnitContext], list[RuleHit]]


def _same_object(f1: Function, f2: Function) -> bool:
    return object_overlap(f1, f2) >= OBJECT_OVERLAP_MIN


def _rule_a(ctx: UnitContext) -> list[RuleHit]:
    """(a) исполняет и strong-контролирует один и тот же объект."""
    hits: list[RuleHit] = []
    for control in ctx.functions:
        if control_strength(control.text, control.executor) != "strong":
            continue
        for executor in ctx.functions:
            if executor is not control:
                if control_strength(executor.text, executor.executor) is not None:
                    continue  # контроль + контроль — не исполнение
            elif len(action_of(control).verbs) < 2:
                continue  # одна функция — только «разрабатывает и утверждает …»
            if not is_execution(executor) or not _same_object(executor, control):
                continue
            if exclusion_reason([executor, control], control=control):
                continue
            pair = [executor] if executor is control else [executor, control]
            hits.append(
                RuleHit(
                    pair,
                    f"исполняет и {', '.join(_strong_verbs(action_of(control)))} "
                    f"«{action_of(control).object_text}»",
                )
            )
    return hits


def _rule_b(ctx: UnitContext) -> list[RuleHit]:
    """(b) инициирует и утверждает один и тот же объект."""
    hits: list[RuleHit] = []
    for approver in ctx.functions:
        if not is_approval(approver):
            continue
        for initiator in ctx.functions:
            if not is_initiation(initiator):
                continue
            if initiator is not approver and is_approval(initiator):
                continue
            if not _same_object(initiator, approver):
                continue
            if exclusion_reason([initiator, approver], control=approver):
                continue
            pair = [initiator] if initiator is approver else [initiator, approver]
            hits.append(
                RuleHit(pair, f"инициирует и утверждает «{action_of(approver).object_text}»")
            )
    return hits


def _rule_c(ctx: UnitContext) -> list[RuleHit]:
    """(c) внутренний аудит выполняет операционную функцию вне мандата аудита."""
    if not ctx.is_audit:
        return []
    mandate = [c for c in ctx.constraints if MANDATE_CONSTRAINT_RE.search(norm(c.text))]
    hits: list[RuleHit] = []
    for fn in ctx.functions:
        kind = operational_kind(fn)
        if kind is None:
            continue
        if FOREIGN_EXECUTOR_RE.search(norm(fn.executor)):
            continue  # исполняет Общество/Президент, не аудит
        if AUDIT_UNIT_RE.search(action_of(fn).object_text):
            continue  # объект — сам аудит (услуги аудита, план аудита): в мандате
        if exclusion_reason([fn]):
            continue
        hits.append(RuleHit([fn, *mandate[:1]], f"внутренний аудит: {kind}"))
    return hits


def _rule_d(ctx: UnitContext) -> list[RuleHit]:
    """(d) контроль возложен на контролируемого: объект strong-контроля — само подразделение,
    его руководитель или его собственная деятельность."""
    hits: list[RuleHit] = []
    for fn in ctx.functions:
        if control_strength(fn.text, fn.executor) != "strong":
            continue
        action = action_of(fn)
        if not ctx.refers_to_self(action):
            continue
        if exclusion_reason([fn], control=fn):
            continue
        hits.append(RuleHit([fn], f"контролирует собственную деятельность: «{action.object_text}»"))
    return hits


def _rule_e(ctx: UnitContext) -> list[RuleHit]:
    """(e) функция нарушает прямой запрет документа: то же действие над тем же объектом."""
    hits: list[RuleHit] = []
    for fn in ctx.functions:
        action = action_of(fn)
        if not action.verbs:
            continue
        for constraint in ctx.constraints:
            banned = action_of(constraint)
            if not (action.verb_stems & banned.verb_stems):
                continue
            if action_overlap(action, banned) < OBJECT_OVERLAP_MIN:
                continue
            if exclusion_reason([fn]):
                continue
            hits.append(
                RuleHit(
                    [fn, constraint],
                    f"запрет п. {clause_number(constraint) or '—'} нарушен: «{banned.object_text}»",
                )
            )
    return hits


RULES: list[tuple[str, str, str, RuleCheck]] = [
    (
        "a",
        "Одно подразделение исполняет и контролирует один объект",
        "исполнитель+контролёр",
        _rule_a,
    ),
    (
        "b",
        "Одно подразделение инициирует и утверждает один объект",
        "инициатор+утверждающий",
        _rule_b,
    ),
    (
        "c",
        "Внутренний аудит выполняет операционную функцию вне мандата",
        "аудитор+оператор",
        _rule_c,
    ),
    ("d", "Контроль возложен на контролируемого", "самоконтроль", _rule_d),
    ("e", "Функция нарушает прямой запрет документа", "запрет+исполнение", _rule_e),
]
DEFAULT_SEVERITY: dict[str, Severity] = {
    "a": "medium",
    "b": "high",
    "c": "high",
    "d": "medium",
    "e": "high",
}
# Одна и та же группа функций под несколькими правилами — остаётся более конкретное.
_SPECIFICITY = ("e", "b", "c", "d", "a")


def is_excluded(pair: Sequence[Function]) -> str | None:
    """Причина исключения пары (исполнитель, контролёр) или одной функции; None — не исключена.
    Контролёр — сторона с контрольным действием, а без него — последняя функция пары."""
    functions = list(pair)
    if not functions:
        return None
    control = next(
        (fn for fn in reversed(functions) if control_strength(fn.text, fn.executor)),
        functions[-1],
    )
    return exclusion_reason(functions, control=control)


# --- сборка находок -------------------------------------------------------------------------


def _contexts(
    functions_by_unit: dict[str, list[Function]],
    constraints: Sequence[Any] | None,
    unit_names: dict[str, str],
) -> list[UnitContext]:
    grouped: dict[str, list[Function]] = {}
    banned: list[Function] = []
    for owner, fn in iter_owned(functions_by_unit):
        if fn.modality == "prohibition":
            banned.append(fn)
        else:
            grouped.setdefault(owner, []).append(fn)
    banned.extend(_as_function(c) for c in constraints or [])
    unique: dict[str, Function] = {}
    for c in banned:
        if c is not None:
            unique.setdefault(c.id, c)
    owners = set(grouped)
    contexts: list[UnitContext] = []
    for owner, functions in grouped.items():
        unit_id = functions[0].unit_id or (None if owner.startswith("executor:") else owner)
        name = unit_names.get(unit_id or "") or None
        ctx = UnitContext(owner, unit_id, name, functions, [])
        ctx.abbreviations = _abbreviations([name, *(fn.executor for fn in functions)])
        ctx.constraints = [c for c in unique.values() if _constraint_applies(c, ctx, owners)]
        contexts.append(ctx)
    return contexts


def _as_function(item: Any) -> Function | None:
    """Запрет как Function (S09 отдаёт Function; schemas.Constraint тоже принимается)."""
    if isinstance(item, Function):
        return item
    try:
        data = item.model_dump() if isinstance(item, BaseModel) else dict(item)
        return Function(
            id=data["id"],
            unit_id=data.get("unit_id"),
            text=data["text"],
            category="duty",
            modality="prohibition",
            executor=data.get("executor"),
            action=None,
            object=None,
            signature=None,
            context_clause_numbers=list(data.get("context_clause_numbers") or []),
            sources=data["sources"],
        )
    except (KeyError, TypeError, ValueError):
        logger.warning("Запрет отброшен: не приводится к Function")
        return None


def explain_payload(
    rule_id: str,
    title: str,
    role_pattern: str,
    units: list[str],
    functions: list[Function],
    unit_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    names = unit_names or {}
    return {
        "rule_id": rule_id,
        "title": title,
        "role_pattern": role_pattern,
        "units": units,
        "functions": [function_payload(fn, names.get(fn.unit_id or "")) for fn in functions],
    }


def _code_explanation(title: str, detail: str, functions: list[Function]) -> str:
    """Объяснение без LLM: правило, что совпало, и дословные цитаты сторон с номерами пунктов."""
    parts = []
    for fn in functions:
        src = fn.sources[0]
        number = f"п. {src.clause_number}" if src.clause_number else "пункт без номера"
        kind = "запрет" if fn.modality == "prohibition" else "функция"
        parts.append(f"{kind} ({number}): «{src.quote.strip()}»")
    return f"{title}: {detail}. " + "; ".join(parts) + "."


def _sources(functions: list[Function]) -> list[Source]:
    seen: set[tuple[str, str]] = set()
    result: list[Source] = []
    for fn in functions:
        for src in fn.sources:
            key = (src.doc_id, src.clause_id)
            if key not in seen:
                seen.add(key)
                result.append(src)
    return result


def find_conflicts(
    functions_by_unit: dict[str, list[Function]],
    llm: LLM,
    constraints: list[Function] | None = None,
    *,
    unit_names: dict[str, str] | None = None,
) -> list[Conflict]:
    """Потенциальные конфликты интересов одной версии. Подтверждённые LLM — `verified=True`;
    сомнения модели или отсутствие ответа — `verified=False` «требует проверки»."""
    if not functions_by_unit or not any(functions_by_unit.values()):
        return []
    names = unit_names or {}
    rule_meta = {rule_id: (title, role) for rule_id, title, role, _ in RULES}

    found: dict[frozenset[str], tuple[str, RuleHit]] = {}
    for ctx in _contexts(functions_by_unit, constraints, names):
        for rule_id, _title, _role, check in RULES:
            for hit in check(ctx):
                key = frozenset(fn.id for fn in hit.functions if fn.modality != "prohibition")
                current = found.get(key)
                if current is None or _SPECIFICITY.index(rule_id) < _SPECIFICITY.index(current[0]):
                    found[key] = (rule_id, hit)
    if not found:
        return []

    order = {rule_id: i for i, (rule_id, *_rest) in enumerate(RULES)}
    hits = sorted(found.values(), key=lambda item: (order[item[0]], item[1].functions[0].id))
    conflicts: list[Conflict] = []
    calls = 0
    for rule_id, hit in hits:
        title, role_pattern = rule_meta[rule_id]
        functions = hit.functions
        units = sorted(
            {fn.unit_id for fn in functions if fn.unit_id and fn.modality != "prohibition"}
        )
        severity: Severity = DEFAULT_SEVERITY[rule_id]
        explanation = _code_explanation(title, hit.detail, functions)
        verified = False
        if calls >= MAX_CONFLICT_CALLS:
            note = f"требует проверки: объяснение не получено (превышен лимит {MAX_CONFLICT_CALLS})"
        else:
            calls += 1
            payload = explain_payload(rule_id, title, role_pattern, units, functions, names)
            try:
                out = call_llm(llm, LLM_NAME, payload, ExplainConflictOut)
            except LLMError as exc:
                note = f"требует проверки: объяснение не получено ({exc})"
            except Exception as exc:  # процесс не падает из-за одной находки
                logger.exception("explain_conflict: сбой на правиле %s", rule_id)
                note = f"требует проверки: объяснение не получено ({type(exc).__name__})"
            else:
                allowed = allowed_numbers(functions)
                text, removed = clean_clause_refs(out.explanation.strip(), allowed)
                note_text, removed_note = clean_clause_refs(out.verification_note.strip(), allowed)
                if removed or removed_note:
                    logger.warning(
                        "explain_conflict: удалены номера пунктов не из находки %s",
                        removed + removed_note,
                    )
                explanation = text or explanation
                severity = out.severity
                verified = bool(out.verified)
                if verified:
                    note = note_text or "подтверждено проверкой LLM"
                else:
                    note = f"требует проверки: {note_text or 'модель не подтвердила конфликт'}"
        conflicts.append(
            Conflict(
                id="",
                rule_id=rule_id,
                title=title,
                role_pattern=role_pattern,
                severity=severity,
                units=units,
                functions=functions,
                explanation=explanation,
                verified=verified,
                verification_note=note,
                sources=_sources(functions),
            )
        )
    conflicts.sort(key=lambda c: not c.verified)  # подтверждённые первыми
    return [c.model_copy(update={"id": f"conflict-{i}"}) for i, c in enumerate(conflicts, start=1)]
