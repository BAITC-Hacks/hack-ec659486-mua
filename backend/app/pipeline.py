"""Оркестратор прогона (spec §2, §4): parsing → units → functions → candidates → verification →
conflicts → conclusion → done | partial | error.

Модули шагов пишут другие сессии параллельно, поэтому они импортируются лениво внутри шага:
- модуля (или нужной функции в нём) ещё нет → шаг пропущен, записан в `missing_steps` с причиной,
  прогон идёт дальше; зависящие от него шаги тоже пропускаются с честной причиной;
- модуль есть, но его импорт падает (сломанная зависимость) → статус `error`;
- LLMError (в mock — нет фикстуры) → статус `error` с русским текстом;
- любое другое исключение внутри шага → шаг не выполнен (`partial`), остальные шаги идут дальше.
`done` — только если выполнены все семь шагов; «изменений не найдено» без полного анализа
не пишется.

Дубли и конфликты ищутся в версии «после»: это структура, которую оценивает аналитик.
В отчёт попадают только находки, чьи источники подтверждены разобранными документами: пункт
(clause_id и номер) и дословная цитата — у самой находки и у обеих её сторон.
"""

import asyncio
import importlib
import logging
import re
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import ModuleType
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from app import store
from app.config import get_settings
from app.llm import LLM, LLMError, redact_secrets
from app.schemas import (
    Clause,
    Conflict,
    Constraint,
    Document,
    Duplicate,
    Function,
    FunctionMatch,
    Report,
    Source,
    UnitChange,
    empty_stats,
)

logger = logging.getLogger(__name__)

# Шаг → (прогресс перед шагом, название для пользователя). Порядок — порядок выполнения.
STEPS: dict[str, tuple[int, str]] = {
    "parsing": (5, "Разбор документов"),
    "units": (15, "Подразделения"),
    "functions": (30, "Функции"),
    "candidates": (45, "Кандидаты"),
    "verification": (65, "Проверка"),
    "conflicts": (80, "Конфликты интересов"),
    "conclusion": (90, "Заключение"),
}
FINAL_STATES = ("done", "partial", "error")

# Роль → модуль. Словарь, а не константы в коде шагов: тест подменяет модуль одной записью.
MODULES: dict[str, str] = {
    "parse": "app.parse.docx",
    "units": "app.units",
    "functions": "app.functions",
    "candidates": "app.candidates",
    "matching": "app.matching",
    "duplicates": "app.duplicates",
    "conflicts": "app.rules.conflicts",
    "conclusion": "app.conclusion",
    "export": "app.export_md",
}

# Шаг выполняется, только если выполнены шаги, от которых он зависит: иначе он работал бы
# на пустом входе и выдавал «ничего не найдено» вместо «не проверено».
REQUIRES: dict[str, tuple[str, ...]] = {
    "parsing": (),
    "units": ("parsing",),
    "functions": ("parsing", "units"),
    "candidates": ("functions",),
    "verification": ("functions", "candidates"),
    "conflicts": ("functions",),
    # Заключение проверяет полноту сам: при неполном анализе пишет честный текст и делает экспорт.
    "conclusion": (),
}

CONCLUSION_NOT_IMPLEMENTED = "Заключение не сформировано: модуль не реализован."

_TASKS: set[asyncio.Task[None]] = set()


class StepSkipped(Exception):
    """Модуль шага или функция в нём ещё не влиты — шаг пропускается, прогон идёт дальше."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class RunFailed(Exception):
    """Прогон продолжать нельзя; текст — для пользователя, по-русски."""


@dataclass
class _Run:
    """Промежуточные результаты шагов одного прогона."""

    run_id: str
    llm: LLM
    docs: dict[str, list[Document]] = field(default_factory=lambda: {"before": [], "after": []})
    unit_changes: list[UnitChange] = field(default_factory=list)
    functions: dict[str, list[Function]] = field(
        default_factory=lambda: {"before": [], "after": []}
    )
    constraints: dict[str, list[Function]] = field(
        default_factory=lambda: {"before": [], "after": []}
    )
    candidates: Any = None
    duplicate_pairs: Any = None
    matches: list[FunctionMatch] = field(default_factory=list)
    duplicates: list[Duplicate] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    conclusion_md: str = ""
    recommendations: list[str] = field(default_factory=list)
    markdown: str | None = None
    completed: list[str] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)

    def skip(self, step: str, reason: str, kind: str = "missing") -> None:
        """kind: missing — модуля нет; failed — шаг упал; dependency — не выполнен шаг-основа."""
        self.skipped.append({"step": step, "reason": reason, "kind": kind})

    @property
    def missing_steps(self) -> list[str]:
        seen: list[str] = []
        for item in self.skipped:
            if item["step"] not in seen:
                seen.append(item["step"])
        return seen


# --- запуск -----------------------------------------------------------------------------------


def start(run_id: str) -> asyncio.Task[None]:
    """Ставит прогон фоновой задачей в текущий цикл событий (ссылка держится до завершения)."""
    task = asyncio.create_task(run_pipeline(run_id), name=f"run-{run_id}")
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return task


async def run_pipeline(run_id: str) -> None:
    """Прогоняет все шаги для записи run_id из store. Исключения наружу не выпускает."""
    record = store.get(run_id)
    if record is None:
        logger.error("Прогон %s: запись не найдена", run_id)
        return
    run = _Run(run_id=run_id, llm=LLM(get_settings()))
    current = "parsing"
    try:
        for step, action in (
            ("parsing", lambda: _parsing(run, record.inputs)),
            ("units", lambda: _units(run)),
            ("functions", lambda: _functions(run)),
            ("candidates", lambda: _candidates(run)),
            ("verification", lambda: _verification(run)),
            ("conflicts", lambda: _conflicts(run)),
            ("conclusion", lambda: _conclusion(run)),
        ):
            current = step
            await _step(run, step, action)
        report = _build_report(run)
        markdown = run.markdown or _fallback_markdown(report)
        store.set_result(run_id, report, run.skipped, markdown)
        missing = run.missing_steps
        store.update_status(
            run_id,
            status="partial" if missing else "done",
            progress=100,
            detail=_partial_detail(run) if missing else "Анализ завершён.",
            missing_steps=missing,
        )
    except RunFailed as exc:
        _fail(run, current, str(exc))
    except LLMError as exc:
        _fail(run, current, _llm_error_text(exc, current, run.llm.mode))
    except Exception as exc:  # фоновая задача не должна умирать молча
        ref = uuid4().hex[:8]
        logger.error(
            "Прогон %s [%s]: %s: %s", run_id, ref, type(exc).__name__, redact_secrets(str(exc))
        )
        _fail(run, current, f"Внутренняя ошибка анализа на шаге «{_title(current)}» (ref {ref}).")


async def _step(run: _Run, step: str, action: Callable[[], Awaitable[None]]) -> None:
    """Обновляет статус и прогресс, проверяет зависимости и выполняет шаг по правилам модуля."""
    progress, title = STEPS[step]
    store.update_status(run.run_id, status=step, progress=progress, detail=f"{title}…")
    blocked = [dep for dep in REQUIRES[step] if dep not in run.completed]
    if blocked:
        names = ", ".join(f"«{_title(dep)}»" for dep in blocked)
        run.skip(step, f"зависит от невыполненных шагов: {names}", "dependency")
        return
    failures_before = len(run.skipped)
    try:
        await action()
    except StepSkipped as exc:
        run.skip(step, exc.reason)
        return
    except (RunFailed, LLMError):
        raise
    except Exception as exc:  # сбой одного шага не роняет прогон
        if step == "parsing":
            raise
        message = redact_secrets(str(exc))[:200]
        logger.error("Прогон %s, шаг %s: %s: %s", run.run_id, step, type(exc).__name__, message)
        run.skip(step, f"шаг завершился ошибкой ({type(exc).__name__}: {message})", "failed")
        return
    if len(run.skipped) == failures_before:
        run.completed.append(step)


# --- шаги -------------------------------------------------------------------------------------


async def _parsing(run: _Run, inputs: dict[str, list[dict[str, str]]]) -> None:
    parse_docx = _function(_module("parse"), "parse_docx")
    for version in ("before", "after"):
        for item in inputs.get(version, []):
            try:
                doc = await asyncio.to_thread(parse_docx, item["path"], version, item["name"])
            except LLMError:
                raise
            except Exception as exc:
                raise RunFailed(
                    f"Не удалось разобрать файл «{item['name']}»: {redact_secrets(str(exc))}"
                ) from exc
            parsed = _coerce(Document, [doc], "документ")
            if not parsed:
                raise RunFailed(f"Разбор файла «{item['name']}» вернул невалидный документ.")
            run.docs[version].append(parsed[0])


async def _units(run: _Run) -> None:
    detect_units = _function(_module("units"), "detect_units")
    # Версия — список документов (положение, ДИ, приказ); S05 объединяет подразделения всех.
    changes = await asyncio.to_thread(detect_units, run.docs["before"], run.docs["after"], run.llm)
    run.unit_changes = _sourced(_coerce(UnitChange, changes, "подразделение"), run, "подразделение")


async def _functions(run: _Run) -> None:
    module = _module("functions")
    extract_all = getattr(module, "extract_all", None)
    extract_functions = getattr(module, "extract_functions", None)
    if not callable(extract_all) and not callable(extract_functions):
        raise StepSkipped(f"в модуле {MODULES['functions']} ещё нет extract_all/extract_functions")
    units = _units_by_version(run.unit_changes)
    for version in ("before", "after"):
        for doc in run.docs[version]:
            if callable(extract_all):
                result = await asyncio.to_thread(extract_all, doc, units[version], run.llm)
            else:
                result = await asyncio.to_thread(extract_functions, doc, None, run.llm)
            functions, constraints = _split_result(result)
            for fn in _sourced(_coerce(Function, functions, "функция"), run, "функция", version):
                # Запрет — ограничение, а не функция: в кандидаты и проверку не идёт.
                target = run.constraints if fn.modality == "prohibition" else run.functions
                target[version].append(fn)
            run.constraints[version].extend(
                _sourced(_coerce(Function, constraints, "ограничение"), run, "ограничение", version)
            )


async def _candidates(run: _Run) -> None:
    module = _module("candidates")
    find_candidates = _function(module, "find_candidates")
    run.candidates = await asyncio.to_thread(
        find_candidates, run.functions["before"], run.functions["after"], run.llm
    )
    find_pairs = getattr(module, "find_duplicate_candidates", None)
    if callable(find_pairs):
        run.duplicate_pairs = await asyncio.to_thread(find_pairs, run.functions["after"])


async def _verification(run: _Run) -> None:
    """Сопоставление до↔после и проверка кандидатов в дубли; то, что не проверено, остаётся
    в отчёте кандидатом с verified=false."""
    try:
        verify_matches = _function(_module("matching"), "verify_matches")
        matches = await asyncio.to_thread(
            verify_matches,
            run.functions["before"],
            run.functions["after"],
            run.candidates,
            run.llm,
            _clauses(run, "after"),
            # Контекст функций «до» и карта подразделений S05: без них S10 не видит `moved`.
            before_clauses=_clauses(run, "before"),
            unit_changes=run.unit_changes,
        )
        run.matches = _sourced(
            _coerce(FunctionMatch, matches, "сопоставление"), run, "сопоставление"
        )
    except StepSkipped as exc:
        run.skip("verification", exc.reason)
    try:
        find_duplicates = _function(_module("duplicates"), "find_duplicates")
        duplicates = await asyncio.to_thread(
            find_duplicates,
            _by_unit(run.functions["after"]),
            run.llm,
            run.duplicate_pairs,
            unit_names=_unit_names(run),
        )
        run.duplicates = _sourced(_coerce(Duplicate, duplicates, "дубль"), run, "дубль")
    except StepSkipped as exc:
        run.skip("verification", exc.reason)


async def _conflicts(run: _Run) -> None:
    find_conflicts = _function(_module("conflicts"), "find_conflicts")
    # Имена подразделений нужны правилам S11: самоконтроль (d) узнаётся по названию.
    conflicts = await asyncio.to_thread(
        find_conflicts,
        _by_unit(run.functions["after"]),
        run.llm,
        run.constraints["after"],
        unit_names=_unit_names(run),
    )
    run.conflicts = _sourced(_coerce(Conflict, conflicts, "конфликт"), run, "конфликт")


async def _conclusion(run: _Run) -> None:
    """Заключение только из фактов предыдущих шагов, затем экспорт .md.

    При неполном анализе LLM не вызывается: заключение по неполным данным выдало бы
    «изменений не найдено» там, где анализ просто не выполнялся.
    """
    upstream = [step for step in STEPS if step != "conclusion" and step not in run.completed]
    if upstream:
        names = ", ".join(f"«{_title(step)}»" for step in upstream)
        run.skip("conclusion", f"не сформировано: не выполнены шаги {names}", "dependency")
        await _export(run)
        return
    try:
        module = _module("conclusion")
        build_facts = _function(module, "build_facts")
        write_conclusion = _function(module, "write_conclusion")
    except StepSkipped as exc:
        run.conclusion_md = CONCLUSION_NOT_IMPLEMENTED
        run.skip("conclusion", exc.reason)
    else:
        facts = await asyncio.to_thread(build_facts, _build_report(run))
        result = await asyncio.to_thread(write_conclusion, facts, run.llm)
        run.conclusion_md = str(_field(result, "conclusion_md") or "").strip()
        run.recommendations = [str(item) for item in _field(result, "recommendations") or []]
    await _export(run)


async def _export(run: _Run) -> None:
    try:
        export_markdown = _function(_module("export"), "export_markdown")
    except StepSkipped as exc:
        run.skip("conclusion", exc.reason)
        return
    run.markdown = await asyncio.to_thread(export_markdown, _build_report(run))


# --- ленивый импорт ---------------------------------------------------------------------------


def _module(role: str) -> ModuleType:
    """Модуль шага: нет самого модуля → StepSkipped; есть, но не импортируется → RunFailed."""
    name = MODULES[role]
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        missing = exc.name or ""
        if missing and (name == missing or name.startswith(missing + ".")):
            raise StepSkipped(f"модуль {name} ещё не реализован") from exc
        raise RunFailed(
            f"Модуль {name} есть, но не загружается: не найдена зависимость «{missing}»."
        ) from exc
    except ImportError as exc:
        raise RunFailed(f"Модуль {name} есть, но не загружается: {exc}.") from exc


def _function(module: ModuleType, attr: str) -> Callable[..., Any]:
    fn = getattr(module, attr, None)
    if not callable(fn):
        raise StepSkipped(f"в модуле {module.__name__} ещё нет функции {attr}")
    return fn


# --- приведение результатов соседей -----------------------------------------------------------


def _coerce[M: BaseModel](model: type[M], items: Any, what: str) -> list[M]:
    """Приводит результат соседнего модуля к модели контракта; невалидное отбрасывается."""
    result: list[M] = []
    for item in items or []:
        try:
            if isinstance(item, model):
                result.append(item)
            elif isinstance(item, BaseModel):
                result.append(model.model_validate(item.model_dump()))
            else:
                result.append(model.model_validate(item))
        except ValidationError as exc:
            logger.warning("Отброшена находка «%s»: не проходит контракт (%s)", what, exc)
    return result


def _split_result(result: Any) -> tuple[list[Any], list[Any]]:
    """extract_* отдаёт (functions, constraints); просто список — только функции."""
    if isinstance(result, tuple) and len(result) == 2:
        return list(result[0] or []), list(result[1] or [])
    return list(result or []), []


def _field(result: Any, name: str) -> Any:
    return result.get(name) if isinstance(result, dict) else getattr(result, name, None)


def _units_by_version(changes: list[UnitChange]) -> dict[str, list[Any]]:
    units: dict[str, dict[str, Any]] = {"before": {}, "after": {}}
    for change in changes:
        if change.unit_before is not None:
            units["before"].setdefault(change.unit_before.id, change.unit_before)
        if change.unit_after is not None:
            units["after"].setdefault(change.unit_after.id, change.unit_after)
    return {version: list(items.values()) for version, items in units.items()}


def _clauses(run: _Run, version: str) -> list[Clause]:
    return [clause for doc in run.docs[version] for clause in doc.clauses]


def _unit_names(run: _Run) -> dict[str, str]:
    """Unit.id → название, обе версии: `Function.unit_id` сам по себе непрозрачен."""
    return {
        unit.id: unit.name
        for change in run.unit_changes
        for unit in (change.unit_before, change.unit_after)
        if unit is not None
    }


def _by_unit(functions: list[Function]) -> dict[str, list[Function]]:
    grouped: dict[str, list[Function]] = {}
    for fn in functions:
        grouped.setdefault(fn.unit_id or "", []).append(fn)
    return grouped


# --- проверка источников ----------------------------------------------------------------------


_QUOTE_MARKS = str.maketrans(dict.fromkeys("«»“”„‟″", '"') | dict.fromkeys("‘’‚‛′", "'"))
_DASHES = re.compile(r"[‐‑‒–—―−]")
_SPACES = re.compile(r"\s+")
_ELLIPSIS = re.compile(r"\.{3,}")
_EDGE = " .,;:\"'"


def _normalized(text: str) -> str:
    """Для сверки цитаты: NFKC (неразрывные пробелы, «…»), кавычки, тире, пробелы, регистр."""
    text = unicodedata.normalize("NFKC", text).translate(_QUOTE_MARKS)
    return _SPACES.sub(" ", _DASHES.sub("-", text)).strip().casefold()


def _quoted(quote: str, text: str) -> bool:
    """Цитата дословно есть в тексте; «...» в цитате — пропуск, части идут в тексте по порядку.

    Кавычки вокруг цитаты и знаки препинания на краях частей не учитываются.
    """
    needle, haystack = _normalized(quote), _normalized(text)
    if needle and needle in haystack:
        return True
    parts = [part.strip(_EDGE) for part in _ELLIPSIS.split(needle)]
    parts = [part for part in parts if part]
    if not parts:
        return False
    position = 0
    for part in parts:
        found = haystack.find(part, position)
        if found < 0:
            return False
        position = found + len(part)
    return True


def _source_ok(source: Source, run: _Run) -> bool:
    """Источник подтверждён документом прогона: документ той же версии, пункт с этим clause_id
    и тем же печатным номером, цитата дословно из текста пункта (или его вводной фразы)."""
    for doc in run.docs.get(source.version, []):
        if doc.id != source.doc_id:
            continue
        for clause in doc.clauses:
            if clause.id != source.clause_id or clause.number != source.clause_number:
                continue
            text = f"{clause.lead_in} {clause.text}" if clause.lead_in else clause.text
            if _quoted(source.quote, text):
                return True
    return False


def _with_sources[M: BaseModel](item: M, run: _Run, version: str | None = None) -> M | None:
    """Только подтверждённые источники (и только версии version, если она задана); None — если
    не осталось ни одного."""
    sources: list[Source] = getattr(item, "sources")
    valid = [
        src
        for src in sources
        if (version is None or src.version == version) and _source_ok(src, run)
    ]
    if not valid:
        return None
    if len(valid) != len(sources):
        logger.warning(
            "%s %s: отброшено неподтверждённых источников: %d",
            type(item).__name__,
            getattr(item, "id", ""),
            len(sources) - len(valid),
        )
        return item.model_copy(update={"sources": valid})
    return item


def _checked[M: BaseModel](item: M, run: _Run, version: str | None = None) -> M | None:
    """Находка с подтверждёнными источниками или None, если подтвердить её нечем.

    Проверяются источники самой находки и обеих её сторон: подразделения «до»/«после»,
    функции сопоставления, пара функций дубля, функции конфликта. Сторона «до» подтверждается
    только документами «до», сторона «после» — только «после». Сторона без подтверждённого
    источника делает находку неподтверждённой: её не показывают.
    """
    update: dict[str, Any] = {}
    if isinstance(item, UnitChange):
        for side, side_version in (("unit_before", "before"), ("unit_after", "after")):
            unit = getattr(item, side)
            if unit is not None:
                if (checked := _with_sources(unit, run, side_version)) is None:
                    return None
                update[side] = checked
    elif isinstance(item, FunctionMatch):
        for side in ("before", "after"):
            functions = [_with_sources(fn, run, side) for fn in getattr(item, side)]
            if any(fn is None for fn in functions):
                return None
            update[side] = functions
    elif isinstance(item, Duplicate):
        for side in ("function_a", "function_b"):
            if (checked := _with_sources(getattr(item, side), run)) is None:
                return None
            update[side] = checked
    elif isinstance(item, Conflict):
        functions = [_with_sources(fn, run) for fn in item.functions]
        if any(fn is None for fn in functions):
            return None
        update["functions"] = functions
    if "sources" in type(item).model_fields:
        if (own := _with_sources(item, run, version)) is None:
            return None
        update["sources"] = getattr(own, "sources")
    return item.model_copy(update=update)


def _sourced[M: BaseModel](
    items: list[M], run: _Run, what: str, version: str | None = None
) -> list[M]:
    """Оставляет у находок только подтверждённые источники; находка, которую подтвердить
    нечем (у самой находки или у любой из её сторон), отбрасывается."""
    kept: list[M] = []
    for item in items:
        checked = _checked(item, run, version)
        if checked is None:
            logger.warning(
                "Отброшена находка «%s» %s: источник не подтверждён документом "
                "(документ, clause_id, номер пункта или цитата)",
                what,
                getattr(item, "id", ""),
            )
            continue
        if isinstance(checked, FunctionMatch):
            checked = _without_prohibitions(checked)
            if checked is None:
                continue
        kept.append(checked)
    return kept


def _without_prohibitions(match: FunctionMatch) -> FunctionMatch | None:
    """Запреты не сопоставляются как функции (они в constraints)."""
    before = [fn for fn in match.before if fn.modality != "prohibition"]
    after = [fn for fn in match.after if fn.modality != "prohibition"]
    if len(before) == len(match.before) and len(after) == len(match.after):
        return match
    logger.warning("Сопоставление %s: убраны функции-запреты", match.id)
    if not before and not after:
        return None
    return match.model_copy(update={"before": before, "after": after})


# --- отчёт ------------------------------------------------------------------------------------


def _unverified(fn: Function, reason: str) -> FunctionMatch:
    """Функция «до» без решения проверки: кандидат в потери, не вывод."""
    return FunctionMatch(
        id=f"unverified-{fn.id}",
        before=[fn],
        after=[],
        kind="one_to_one",
        status="lost",
        verified=False,
        verification="lexical",
        confidence=0.0,
        note=f"требует проверки: {reason}",
        sources=fn.sources,
    )


def _function_matches(run: _Run) -> list[FunctionMatch]:
    """Результат проверки плюс непроверенные кандидаты для функций «до», не получивших решения."""
    covered = {fn.id for match in run.matches for fn in match.before}
    if "verification" in run.missing_steps and not run.matches:
        related = [item for item in run.skipped if item["step"] in ("candidates", "verification")]
        causes = [item for item in related if item["kind"] != "dependency"] or related
        reason = "сопоставление не выполнялось — " + "; ".join(item["reason"] for item in causes)
    else:
        reason = "нет решения проверки для этой функции"
    extra = [_unverified(fn, reason) for fn in run.functions["before"] if fn.id not in covered]
    return [*run.matches, *extra]


def _constraint(fn: Function) -> Constraint:
    return Constraint(
        id=fn.id,
        unit_id=fn.unit_id,
        text=fn.text,
        executor=fn.executor,
        modality="prohibition",
        sources=fn.sources,
    )


def _build_report(run: _Run) -> Report:
    matches = _function_matches(run) if "functions" in run.completed else []
    constraints = [
        _constraint(fn) for version in ("before", "after") for fn in run.constraints[version]
    ]
    report = Report(
        run_id=run.run_id,
        created_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        before_documents=run.docs["before"],
        after_documents=run.docs["after"],
        unit_changes=run.unit_changes,
        function_matches=matches,
        duplicates=run.duplicates,
        conflicts=run.conflicts,
        constraints=constraints,
        conclusion_md=run.conclusion_md or _not_formed(run),
        recommendations=run.recommendations,
        stats=empty_stats(),
    )
    report.stats = _stats(run, report)
    return report


def _stats(run: _Run, report: Report) -> dict[str, int]:
    """Счётчики статусов считают только проверенные находки; непроверенные — отдельно."""
    stats = empty_stats()
    changes = report.unit_changes
    stats["units_before"] = len({c.unit_before.id for c in changes if c.unit_before is not None})
    stats["units_after"] = len({c.unit_after.id for c in changes if c.unit_after is not None})
    for status in ("kept", "transformed", "created", "abolished"):
        stats[f"units_{status}"] = sum(1 for c in changes if c.status == status)
    stats["functions_before"] = len(run.functions["before"])
    stats["functions_after"] = len(run.functions["after"])
    stats["matches"] = len(report.function_matches)
    verified = [m for m in report.function_matches if m.verified]
    for status in ("kept", "changed", "lost", "new", "moved"):
        stats[status] = sum(1 for m in verified if m.status == status)
    stats["duplicates"] = sum(1 for d in report.duplicates if d.verified)
    stats["conflicts"] = sum(1 for c in report.conflicts if c.verified)
    stats["unverified_candidates"] = sum(
        1
        for finding in (*report.function_matches, *report.duplicates, *report.conflicts)
        if not finding.verified
    )
    stats["constraints"] = len(report.constraints)
    stats["skipped"] = len(run.missing_steps)
    return stats


def _not_formed(run: _Run) -> str:
    """Честный текст заключения, когда анализ выполнен не полностью."""
    missing = [step for step in run.missing_steps if step != "conclusion"]
    if not missing:
        return ""
    lines = [
        "Заключение не сформировано: анализ выполнен не полностью, выводы по неполным данным "
        "не делаются. Не выполнены шаги:",
        "",
    ]
    for item in run.skipped:
        if item["step"] != "conclusion":
            lines.append(f"- {_title(item['step'])}: {item['reason']}")
    return "\n".join(lines)


def _fallback_markdown(report: Report) -> str:
    return (
        f"# Заключение ОргДифф — запуск {report.run_id}\n\n{report.conclusion_md}".rstrip() + "\n"
    )


def _partial_detail(run: _Run) -> str:
    """Какие шаги не выполнены и первопричины (без каскада «зависит от …»)."""
    steps = ", ".join(f"«{_title(step)}»" for step in run.missing_steps)
    causes = "; ".join(
        f"{_title(item['step'])}: {item['reason']}"
        for item in run.skipped
        if item["kind"] != "dependency"
    )
    return f"Анализ выполнен частично, не выполнены шаги {steps}. Причина — {causes}."


def _fail(run: _Run, step: str, message: str) -> None:
    order = list(STEPS)
    remaining = order[order.index(step) :] if step in order else []
    missing = [*run.missing_steps, *[s for s in remaining if s not in run.missing_steps]]
    store.update_status(run.run_id, status="error", detail=message, missing_steps=missing)


_FIXTURE_RE = re.compile(r"([\w./\\-]*mocks[/\\][\w./\\-]+|[\w./\\-]+\.json)")


def _llm_error_text(exc: LLMError, step: str, mode: str) -> str:
    """Русский текст ошибки LLM для пользователя; в mock без фикстуры — подсказка про ключ."""
    message = redact_secrets(str(exc))
    lowered = message.lower()
    if mode == "mock" and any(key in lowered for key in ("fixture", "фикстур", "mocks")):
        found = _FIXTURE_RE.search(message)
        name = found.group(1) if found else message
        if "mocks/" in name:
            name = "mocks/" + name.split("mocks/", 1)[1]
        return (
            f"Нет фикстуры {name}, для своих документов нужен ключ OpenAI в .env "
            f"(OPENAI_API_KEY и LLM_MODE=live). Шаг: «{_title(step)}»."
        )
    return f"Языковая модель не ответила на шаге «{_title(step)}»: {message}"


def _title(step: str) -> str:
    return STEPS.get(step, (0, step))[1]
