"""P4b «Проверка» (spec §2 P4b, §2а, §5 verify_matches / confirm_loss): решение по кандидатам.

Кандидаты (`app.candidates`) только сужают круг — статус ставит этот модуль:
1. Точное совпадение текста решается кодом, но не автоматически: сначала сверяются модальность,
   вводная фраза родительского пункта (`lead_in`) и владелец (подразделение по карте
   `unit_changes` из S05, иначе исполнитель). Тот же владелец → `kept`; другое подразделение →
   `moved` (`verification = exact` по содержанию, в `note` — перенос). Иначе — в LLM.
2. Остальное — LLM `verify_matches`: одна функция «до» + её кандидаты «после» (≤ 5) →
   kept / changed / moved / split / merge / partial / none. Код проверяет ответ: `after_ids`
   только из переданных, цитаты — подстроки переданных пунктов, `moved` — только если
   подразделение действительно другое.
3. `none` или пустые кандидаты → `confirm_loss`: второй поиск по ВСЕМ функциям и сырым пунктам
   «после», LLM подтверждает отсутствие с ближайшим пунктом. Потеря `verified = True` — только
   так; нет ответа / невалидный ответ / `lost = false` / лимит → кандидат в потери
   (`verified = False`, в `note` — причина).
4. Поиск в обе стороны: для каждой функции «после» ищутся кандидаты среди всех «до»; ближайшая
   функция «до» получает её в свой список кандидатов. `new` — только функциям «после», не
   связанным ни с одной «до»; проверенной новой она считается, если её ближайшая «до» проверена
   и связь не подтвердила (или обратный поиск ничего не нашёл).
5. Связи один-ко-многим: компоненты связности графа подтверждённых связей → один
   `FunctionMatch` на компоненту (split / merge / partial), каждая функция — ровно в одном.

Mock-режим: `mocks/<вызов>/<hash>.json`, `hash = sha256(json.dumps(payload, ensure_ascii=False,
sort_keys=True))[:16]`; нет файла → `LLMError` с именем файла → «нет ответа проверки»,
прогон не падает. Live с `LLM_RECORD_MOCKS=1` сохраняет ответы модели в те же файлы (S15).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.candidates import (
    BM25,
    TOP_K,
    Candidate,
    find_candidates,
    normalize_text,
    rank_candidates,
    tokenize,
)
from app.llm import LLM, MOCKS_DIR, LLMError, strict_schema, validate_output
from app.schemas import (
    Clause,
    Function,
    FunctionMatch,
    FunctionMatchKind,
    FunctionMatchStatus,
    Source,
    UnitChange,
    Verification,
)

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
RECORD_ENV = "LLM_RECORD_MOCKS"
MAX_VERIFY_CALLS = 400  # вызовов verify_matches + confirm_loss на один прогон
MAX_CANDIDATES = TOP_K
CONTEXT_MAX = 3  # пунктов контекста в запросе
CONTEXT_TEXT_MAX = 600  # символов текста пункта контекста (дословный префикс)
NEAREST_K = 5

CONFIDENCE: dict[str, float] = {
    "exact": 1.0,
    "exact_moved": 0.9,
    "kept": 0.9,
    "moved": 0.9,
    "changed": 0.8,
    "split": 0.8,
    "merge": 0.8,
    "partial": 0.6,
}
LOST_CONFIDENCE = 0.85
NEW_CONFIDENCE = 0.7
UNVERIFIED_CONFIDENCE = 0.4

Decision = Literal["kept", "changed", "moved", "split", "merge", "partial", "none"]

# --- Схемы ответов LLM (strict). Берутся из llm_schemas.py (S13), если он уже влит. ---------

try:  # pragma: no cover - ветка зависит от порядка мержа волны 3
    from app.llm_schemas import ConfirmLossOut, VerifyMatchesOut  # type: ignore[attr-defined]
except ImportError:

    class VerifyMatchesOut(BaseModel):  # type: ignore[no-redef]
        model_config = ConfigDict(extra="forbid")

        decision: Decision
        after_ids: list[str]
        rationale: str
        quotes: list[str]

    class ConfirmLossOut(BaseModel):  # type: ignore[no-redef]
        model_config = ConfigDict(extra="forbid")

        lost: bool
        nearest_clause_number: str | None
        nearest_quote: str
        rationale: str


# --- LLM с фикстурами по хэшу входа ---------------------------------------------------------


class _LimitReached(Exception):
    """Превышен MAX_VERIFY_CALLS: оставшиеся функции остаются непроверенными."""


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
        logger.debug("matching mock: %s/%s", name, path.name)
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
            logger.info("matching: ответ '%s' сохранён как фикстура %s", name, path.name)
    return validate_output(model, data, name)


# --- Контекст прогона -----------------------------------------------------------------------


def _norm(value: str | None) -> str:
    return normalize_text(value or "")


def _norm_lead(value: str | None) -> str:
    """Вводная фраза без номеров пунктов: «5.3. Директор …:» и «5.4. Директор …:» совпадают."""
    return " ".join(re.sub(r"\d+", " ", _norm(value)).split())


def _quote_key(value: str) -> str:
    value = value.lower().replace("ё", "е")
    value = re.sub(r"[«»\"“”„']", "", value)
    return re.sub(r"\s+", " ", value).strip(" .;:,")


def _doc_prefix(clause_id: str) -> str:
    return clause_id.split(":", 1)[0]


@dataclass
class _Ctx:
    llm: LLM
    before: list[Function]
    after: list[Function]
    after_clauses: list[Clause]
    clauses_by_id: dict[str, Clause]
    clauses_by_number: dict[tuple[str, str], Clause]
    unit_names: dict[str, str] = field(default_factory=dict)
    lineage: dict[tuple[str, str], str] = field(default_factory=dict)
    known_before: set[str] = field(default_factory=set)
    known_after: set[str] = field(default_factory=set)
    calls: int = 0
    _fn_index: BM25 | None = None
    _clause_index: BM25 | None = None

    @classmethod
    def build(
        cls,
        llm: LLM,
        before: list[Function],
        after: list[Function],
        after_clauses: list[Clause] | None,
        before_clauses: list[Clause] | None,
        unit_changes: list[UnitChange] | None,
    ) -> _Ctx:
        all_clauses = list(before_clauses or []) + list(after_clauses or [])
        ctx = cls(
            llm=llm,
            before=before,
            after=after,
            after_clauses=list(after_clauses or []),
            clauses_by_id={c.id: c for c in all_clauses},
            clauses_by_number={
                (_doc_prefix(c.id), c.number): c for c in all_clauses if c.number is not None
            },
        )
        for change in unit_changes or []:
            ub, ua = change.unit_before, change.unit_after
            if ub is not None:
                ctx.unit_names[ub.id] = ub.name
                ctx.known_before.add(ub.id)
            if ua is not None:
                ctx.unit_names[ua.id] = ua.name
                ctx.known_after.add(ua.id)
            if ub is not None and ua is not None:
                ctx.lineage[(ub.id, ua.id)] = change.status
        return ctx

    # --- пункты и описания ---

    def clause_of(self, fn: Function) -> Clause | None:
        return self.clauses_by_id.get(fn.sources[0].clause_id)

    def context_of(self, fn: Function) -> list[dict[str, str]]:
        prefix = fn.sources[0].doc_id
        items: list[dict[str, str]] = []
        for number in fn.context_clause_numbers:
            clause = self.clauses_by_number.get((prefix, number))
            if clause is None or number == fn.sources[0].clause_number:
                continue
            items.append({"number": number, "text": clause.text[:CONTEXT_TEXT_MAX]})
            if len(items) >= CONTEXT_MAX:
                break
        return items

    def unit_label(self, unit_id: str | None) -> str | None:
        if unit_id is None:
            return None
        return self.unit_names.get(unit_id, unit_id)

    def describe(self, fn: Function) -> dict[str, Any]:
        src = fn.sources[0]
        clause = self.clause_of(fn)
        return {
            "id": fn.id,
            "unit": self.unit_label(fn.unit_id),
            "executor": fn.executor,
            "modality": fn.modality,
            "text": fn.text,
            "quote": src.quote,
            "clause_number": src.clause_number,
            "section_path": list(clause.section_path) if clause else [],
            "lead_in": clause.lead_in if clause else None,
            "context": self.context_of(fn),
        }

    # --- владелец функции ---

    def relation(self, fb: Function, fa: Function) -> str:
        """same / transformed / different / unknown — сопоставлен ли владелец «до» с «после»."""
        ub, ua = fb.unit_id, fa.unit_id
        if ub is not None and ua is not None:
            if ub == ua:
                return "same"
            status = self.lineage.get((ub, ua))
            if status is not None:
                return "same" if status == "kept" else "transformed"
            if ub in self.known_before and ua in self.known_after:
                return "different"
        eb, ea = _norm(fb.executor), _norm(fa.executor)
        if ub is None and ua is None and eb == ea:
            return "same"
        if eb and eb == ea:
            return "same"
        return "unknown"

    # --- второй поиск по всему документу «после» ---

    def nearest_functions(self, fn: Function) -> list[Function]:
        if self._fn_index is None:
            self._fn_index = BM25([tokenize(f.text) for f in self.after])
        return [self.after[i] for i, _ in self._fn_index.top(tokenize(fn.text), NEAREST_K)]

    def nearest_clauses(self, fn: Function) -> list[Clause]:
        if not self.after_clauses:
            return []
        if self._clause_index is None:
            self._clause_index = BM25([tokenize(c.text) for c in self.after_clauses])
        query = tokenize(f"{fn.text} {fn.sources[0].quote}")
        return [self.after_clauses[i] for i, _ in self._clause_index.top(query, NEAREST_K)]

    # --- бюджет вызовов ---

    def call(self, name: str, payload: dict[str, Any], model: type[BaseModel]) -> Any:
        if self.calls >= MAX_VERIFY_CALLS:
            raise _LimitReached
        self.calls += 1
        return _call_llm(self.llm, name, payload, model)


def _texts_of(described: list[dict[str, Any]]) -> list[str]:
    texts: list[str] = []
    for item in described:
        texts.extend(t for t in (item.get("text"), item.get("quote"), item.get("lead_in")) if t)
        texts.extend(c["text"] for c in item.get("context", []))
    return texts


def _quote_ok(quote: str, texts: list[str]) -> bool:
    key = _quote_key(quote)
    return bool(key) and any(key in _quote_key(t) for t in texts)


def _ref(fn: Function) -> str:
    number = fn.sources[0].clause_number
    return f"п. {number}" if number else f"блок {fn.sources[0].clause_id}"


def _merge_sources(functions: list[Function]) -> list[Source]:
    seen: set[tuple[str, str]] = set()
    merged: list[Source] = []
    for fn in functions:
        for src in fn.sources:
            key = (src.clause_id, src.quote)
            if key not in seen:
                seen.add(key)
                merged.append(src)
    return merged


# --- Решения ---------------------------------------------------------------------------------


@dataclass
class _Link:
    before_id: str
    after_ids: list[str]
    decision: str  # kept / changed / moved / split / merge / partial
    verification: Verification
    confidence: float
    rationale: str


@dataclass
class _Review:
    """Что видела проверка функции «до»: кандидаты, показанные LLM или решённые кодом."""

    presented: set[str]
    how: Literal["llm", "exact"]


def _candidate_ids(items: Any) -> list[tuple[str, list[str]]]:
    result: list[tuple[str, list[str]]] = []
    for item in items or []:
        if isinstance(item, Candidate):
            result.append((item.after_id, list(item.reasons)))
        elif isinstance(item, dict) and item.get("after_id"):
            result.append((str(item["after_id"]), list(item.get("reasons") or [])))
    return result


def _candidate_lists(
    before: list[Function],
    after: list[Function],
    candidates: dict[str, list[Candidate]] | None,
    ctx: _Ctx,
) -> dict[str, list[str]]:
    """Кандидаты «после» по каждой «до»: переданные S08 + недостающие + из обратного поиска."""
    after_ids = {fn.id for fn in after}
    given = candidates if isinstance(candidates, dict) else {}
    missing = [fn for fn in before if fn.id not in given]
    extra = find_candidates(missing, after, ctx.llm) if missing else {}
    lists: dict[str, list[str]] = {}
    for fn in before:
        ids: list[str] = []
        for after_id, _reasons in _candidate_ids(given.get(fn.id, extra.get(fn.id, []))):
            if after_id not in after_ids:
                logger.warning("verify_matches: кандидат %s не из функций «после»", after_id)
            elif after_id not in ids:
                ids.append(after_id)
        lists[fn.id] = ids[:MAX_CANDIDATES]
    return lists


def _augment(lists: dict[str, list[str]], reverse: dict[str, list[Candidate]], ctx: _Ctx) -> None:
    """Обратный поиск: функция «после» попадает в список своей ближайшей функции «до»."""
    by_after = {fn.id: fn for fn in ctx.after}
    added: dict[str, list[str]] = {}
    for fa in ctx.after:
        rev = reverse.get(fa.id) or []
        if not rev:
            continue
        top = rev[0].after_id  # в обратном поиске это id функции «до»
        if top in lists and fa.id not in lists[top]:
            added.setdefault(top, []).append(fa.id)
    for before_id, extra in added.items():
        current = lists[before_id]
        before_fn = next(fn for fn in ctx.before if fn.id == before_id)
        exact = [a for a in current if _norm(by_after[a].text) == _norm(before_fn.text)]
        rest = [a for a in current if a not in exact]
        merged = exact + extra[: max(0, MAX_CANDIDATES - len(exact))]
        merged += rest[: max(0, MAX_CANDIDATES - len(merged))]
        lists[before_id] = merged


def _exact_link(fb: Function, cands: list[Function], ctx: _Ctx, claimed: set[str]) -> _Link | None:
    """Дословное совпадение, решаемое кодом: модальность, lead_in и владелец сверены."""
    key = _norm(fb.text)
    clause_b = ctx.clause_of(fb)
    same_owner: list[Function] = []
    other_owner: list[Function] = []
    for fa in cands:
        if fa.id in claimed or _norm(fa.text) != key or fa.modality != fb.modality:
            continue
        clause_a = ctx.clause_of(fa)
        if clause_b is not None and clause_a is not None and clause_b.modality != clause_a.modality:
            continue  # та же строка под другим родительским пунктом (например, запретом)
        relation = ctx.relation(fb, fa)
        if relation in ("same", "transformed"):
            lead_b = _norm_lead(clause_b.lead_in) if clause_b else None
            lead_a = _norm_lead(clause_a.lead_in) if clause_a else None
            executor_ok = (
                not fb.executor or not fa.executor or _norm(fb.executor) == _norm(fa.executor)
            )
            if executor_ok and (lead_b is None or lead_a is None or lead_b == lead_a):
                same_owner.append(fa)
        elif relation == "different":
            other_owner.append(fa)
    if same_owner:
        fa = same_owner[0]
        return _Link(
            fb.id,
            [fa.id],
            "kept",
            "exact",
            CONFIDENCE["exact"],
            "Текст совпадает дословно; модальность, вводная фраза и владелец те же.",
        )
    if len(other_owner) == 1:
        fa = other_owner[0]
        return _Link(
            fb.id,
            [fa.id],
            "moved",
            "exact",
            CONFIDENCE["exact_moved"],
            "Текст совпадает дословно, но функция закреплена за другим подразделением.",
        )
    return None


@dataclass
class _Outcome:
    link: _Link | None = None
    none_note: str | None = None  # проверка сказала «среди кандидатов нет»
    failure: str | None = None  # проверка не состоялась или ответ невалиден


def _verify_one(fb: Function, cands: list[Function], ctx: _Ctx) -> _Outcome:
    described = [ctx.describe(fa) for fa in cands]
    payload = {"before": ctx.describe(fb), "candidates": described}
    try:
        out = ctx.call("verify_matches", payload, VerifyMatchesOut)
    except _LimitReached:
        return _Outcome(
            failure=f"лимит пакета: проверка не выполнена (MAX_VERIFY_CALLS = {MAX_VERIFY_CALLS})"
        )
    except LLMError as exc:
        logger.warning("verify_matches %s: %s", fb.id, exc)
        return _Outcome(failure=f"нет ответа проверки ({exc})")

    allowed = [fa.id for fa in cands]
    ids: list[str] = []
    for after_id in out.after_ids:
        if after_id in allowed and after_id not in ids:
            ids.append(after_id)
        elif after_id not in allowed:
            logger.warning(
                "verify_matches %s: after_id %r не из переданных кандидатов — отброшен",
                fb.id,
                after_id,
            )
    texts = _texts_of([payload["before"], *described])
    bad_quotes = [q for q in out.quotes if not _quote_ok(q, texts)]
    for quote in bad_quotes:
        logger.warning("verify_matches %s: цитата не из переданных пунктов: %r", fb.id, quote[:80])
    rationale = out.rationale.strip()

    if out.decision == "none":
        refs = ", ".join(_ref(fa) for fa in cands)
        return _Outcome(
            none_note=f"Кандидаты «после» ({refs}) проверены — совпадения нет: {rationale}"
        )
    if not ids:
        return _Outcome(
            failure=f"ответ проверки невалиден: решение «{out.decision}» без функций «после» "
            "из переданных кандидатов"
        )
    exact_ids = {fa.id for fa in cands if _norm(fa.text) == _norm(fb.text)}
    verification: Verification = (
        "exact" if out.decision == "kept" and len(ids) == 1 and ids[0] in exact_ids else "llm"
    )
    confidence = CONFIDENCE["exact"] if verification == "exact" else CONFIDENCE[out.decision]
    if bad_quotes:
        rationale += f" (цитат не из пунктов отброшено: {len(bad_quotes)})"
    if out.decision in ("kept", "changed", "moved") and len(ids) > 1:
        logger.warning(
            "verify_matches %s: «%s» с несколькими функциями «после»", fb.id, out.decision
        )
    return _Outcome(link=_Link(fb.id, ids, out.decision, verification, confidence, rationale))


# --- Сборка FunctionMatch ---------------------------------------------------------------------


def _assignment(befores: list[Function], afters: list[Function], ctx: _Ctx) -> tuple[str, str]:
    """(код, текст) изменения назначения: same / transformed / moved / executor / unknown."""
    relations = {ctx.relation(fb, fa) for fb in befores for fa in afters}
    units_b = [ctx.unit_label(fn.unit_id) for fn in befores if fn.unit_id]
    units_a = [ctx.unit_label(fn.unit_id) for fn in afters if fn.unit_id]
    side_b = ", ".join(dict.fromkeys(u for u in units_b if u)) or "—"
    side_a = ", ".join(dict.fromkeys(u for u in units_a if u)) or "—"
    arrow = f"{side_b} → {side_a}"
    if "different" in relations:
        return "moved", f"перенесено ({arrow})"
    if "transformed" in relations:
        return "transformed", f"передано преобразованному подразделению ({arrow})"
    exec_b = {_norm(fn.executor) for fn in befores if fn.executor}
    exec_a = {_norm(fn.executor) for fn in afters if fn.executor}
    if exec_b and exec_a and exec_b != exec_a:
        names_b = ", ".join(dict.fromkeys(fn.executor for fn in befores if fn.executor))
        names_a = ", ".join(dict.fromkeys(fn.executor for fn in afters if fn.executor))
        return "executor", f"изменён исполнитель ({names_b} → {names_a})"
    if relations == {"unknown"}:
        return "unknown", "не установлено (нет карты подразделений)"
    return "same", "сохранено"


_CONTENT = {
    "kept": "сохранено",
    "moved": "сохранено",
    "changed": "изменено",
    "split": "разделено",
    "merge": "объединено с другими функциями «до»",
    "partial": "совпадает частично",
}


def _component_match(
    idx: int, befores: list[Function], afters: list[Function], links: list[_Link], ctx: _Ctx
) -> FunctionMatch:
    decisions = [link.decision for link in links]
    assign_code, assign_text = _assignment(befores, afters, ctx)
    kind: FunctionMatchKind
    status: FunctionMatchStatus
    if len(befores) > 1:
        kind, status = "merge", "changed"
        content = f"объединено: {len(befores)} функции «до» → {len(afters)} «после»"
        if len(afters) > 1:
            content += " (связь многие-ко-многим)"
    elif "partial" in decisions:
        kind, status = "partial", "changed"
        content = _CONTENT["partial"]
    elif len(afters) > 1:
        kind, status = "split", "changed"
        content = f"разделено на {len(afters)} функции «после»"
    elif "merge" in decisions:
        kind, status = "merge", "changed"
        content = _CONTENT["merge"]
    else:
        kind = "one_to_one"
        decision = decisions[0]
        if decision == "split":
            decision = "changed"  # split с одной функцией «после» — это изменение
        status = decision  # type: ignore[assignment]
        content = _CONTENT[decision]
    downgrade = ""
    if kind == "one_to_one":
        if status == "moved" and assign_code in ("same", "transformed", "executor"):
            status = "changed"
            downgrade = " Проверка указала перенос, но подразделение то же — статус «изменена»."
        elif status in ("kept", "changed") and assign_code == "moved":
            status = "moved"
    verification: Verification = (
        "exact" if all(link.verification == "exact" for link in links) else "llm"
    )
    confidence = min(link.confidence for link in links)
    rationale = " ".join(dict.fromkeys(link.rationale for link in links if link.rationale))
    note = f"содержание: {content}; назначение: {assign_text}. {rationale}{downgrade}".strip()
    return FunctionMatch(
        id=f"fm-{idx}",
        before=befores,
        after=afters,
        kind=kind,
        status=status,
        verified=True,
        verification=verification,
        confidence=confidence,
        note=note,
        sources=_merge_sources(befores + afters),
    )


def _unverified_lost(idx: int, fn: Function, reason: str) -> FunctionMatch:
    return FunctionMatch(
        id=f"fm-{idx}",
        before=[fn],
        after=[],
        kind="one_to_one",
        status="lost",
        verified=False,
        verification="lexical",
        confidence=UNVERIFIED_CONFIDENCE,
        note=f"Кандидат в потери — требует проверки: {reason}",
        sources=_merge_sources([fn]),
    )


def _confirm_loss(idx: int, fn: Function, ctx: _Ctx, prefix: str = "") -> FunctionMatch:
    lead = f"{prefix.rstrip('. ')}. " if prefix else ""
    check = f"{lead}Проверка по всему документу «после»"
    near_fns = ctx.nearest_functions(fn)
    near_clauses = ctx.nearest_clauses(fn)
    payload = {
        "before": ctx.describe(fn),
        "nearest_functions": [
            {
                "id": fa.id,
                "unit": ctx.unit_label(fa.unit_id),
                "text": fa.text,
                "clause_number": fa.sources[0].clause_number,
            }
            for fa in near_fns
        ],
        "nearest_clauses": [
            {"number": c.number or c.id, "text": c.text[:CONTEXT_TEXT_MAX]} for c in near_clauses
        ],
    }
    allowed = {item["number"] for item in payload["nearest_clauses"]}
    allowed |= {
        item["clause_number"] for item in payload["nearest_functions"] if item["clause_number"]
    }
    try:
        out = ctx.call("confirm_loss", payload, ConfirmLossOut)
    except _LimitReached:
        return _unverified_lost(idx, fn, f"{check}: лимит пакета — не выполнена.")
    except LLMError as exc:
        logger.warning("confirm_loss %s: %s", fn.id, exc)
        return _unverified_lost(idx, fn, f"{check}: нет ответа проверки ({exc})")

    number = (out.nearest_clause_number or "").strip() or None
    if number is not None and number not in allowed:
        logger.warning("confirm_loss %s: пункт %r не из переданных", fn.id, number)
        return _unverified_lost(
            idx, fn, f"{check}: ответ невалиден — пункт {number} не из переданных."
        )
    texts = [c["text"] for c in payload["nearest_clauses"]]
    texts += [f["text"] for f in payload["nearest_functions"]]
    quote = out.nearest_quote.strip()
    if quote and not _quote_ok(quote, texts):
        logger.warning("confirm_loss %s: цитата не из переданных пунктов — опущена", fn.id)
        quote = ""
    nearest = (
        f"Ближайший пункт «после»: {number}" + (f" — «{quote}»" if quote else "") + "."
        if number
        else "Похожего пункта в документе «после» нет."
    )
    rationale = out.rationale.strip()
    if out.lost:
        return FunctionMatch(
            id=f"fm-{idx}",
            before=[fn],
            after=[],
            kind="one_to_one",
            status="lost",
            verified=True,
            verification="llm",
            confidence=LOST_CONFIDENCE,
            note=f"{check}: {rationale} {nearest}".strip(),
            sources=_merge_sources([fn]),
        )
    where = f"ближайший пункт {number}" if number else "похожий пункт не назван"
    return _unverified_lost(
        idx,
        fn,
        f"{check}: низкая уверенность — {where}, пара не подтверждена. "
        f"{rationale} {nearest}".strip(),
    )


def _new_match(idx: int, fa: Function, verified: bool, verification: Verification, note: str):
    return FunctionMatch(
        id=f"fm-{idx}",
        before=[],
        after=[fa],
        kind="one_to_one",
        status="new",
        verified=verified,
        verification=verification,
        confidence=NEW_CONFIDENCE if verified else UNVERIFIED_CONFIDENCE,
        note=note,
        sources=_merge_sources([fa]),
    )


# --- Публичные функции (S08 зовёт их по именам) ----------------------------------------------


def verify_matches(
    before: list[Function],
    after: list[Function],
    candidates: dict[str, list[Candidate]] | None,
    llm: LLM | None,
    after_clauses: list[Clause] | None = None,
    *,
    before_clauses: list[Clause] | None = None,
    unit_changes: list[UnitChange] | None = None,
) -> list[FunctionMatch]:
    """Сопоставление функций до↔после: каждая функция — ровно в одном `FunctionMatch`.

    `after_clauses` — все пункты документов «после» (второй поиск перед признанием потери);
    без них второй поиск идёт только по функциям «после». `before_clauses` дают проверке
    `section_path`/`lead_in`/контекст функций «до», `unit_changes` (S05) — карту подразделений
    для `moved`; оба необязательны.
    """
    before = [fn for fn in before if fn.modality != "prohibition"]
    after = [fn for fn in after if fn.modality != "prohibition"]
    if not before and not after:
        return []
    ctx = _Ctx.build(llm or LLM(), before, after, after_clauses, before_clauses, unit_changes)
    by_after = {fn.id: fn for fn in after}

    lists = _candidate_lists(before, after, candidates, ctx)
    reverse = rank_candidates(after, before, ctx.llm) if before and after else {}
    _augment(lists, reverse, ctx)

    links: list[_Link] = []
    reviews: dict[str, _Review] = {}
    lost_or_failed: dict[str, FunctionMatch] = {}
    claimed_exact: set[str] = set()
    for fb in before:
        cands = [by_after[a] for a in lists.get(fb.id, [])]
        if not cands:
            lost_or_failed[fb.id] = _confirm_loss(
                0, fb, ctx, "У функции нет кандидатов среди «после»."
            )
            continue
        exact = _exact_link(fb, cands, ctx, claimed_exact)
        if exact is not None:
            links.append(exact)
            claimed_exact.update(exact.after_ids)
            reviews[fb.id] = _Review({fa.id for fa in cands}, "exact")
            continue
        outcome = _verify_one(fb, cands, ctx)
        if outcome.link is not None:
            links.append(outcome.link)
            reviews[fb.id] = _Review({fa.id for fa in cands}, "llm")
        elif outcome.none_note is not None:
            reviews[fb.id] = _Review({fa.id for fa in cands}, "llm")
            lost_or_failed[fb.id] = _confirm_loss(0, fb, ctx, outcome.none_note)
        else:
            refs = ", ".join(f"{_ref(fa)} ({fa.id})" for fa in cands)
            lost_or_failed[fb.id] = _unverified_lost(
                0, fb, f"{outcome.failure}. Кандидаты «после»: {refs}."
            )

    # Компоненты связности: «до» и «после», связанные подтверждёнными связями.
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        while parent.setdefault(node, node) != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for link in links:
        for after_id in link.after_ids:
            parent[find(f"b:{link.before_id}")] = find(f"a:{after_id}")
    comp_links: dict[str, list[_Link]] = {}
    for link in links:
        comp_links.setdefault(find(f"b:{link.before_id}"), []).append(link)

    matches: list[FunctionMatch] = []
    emitted: set[str] = set()
    for fb in before:
        if fb.id in lost_or_failed:
            matches.append(lost_or_failed[fb.id].model_copy(update={"id": f"fm-{len(matches)}"}))
            continue
        root = find(f"b:{fb.id}")
        if root in emitted or root not in comp_links:
            continue
        emitted.add(root)
        comp = comp_links[root]
        before_ids = {link.before_id for link in comp}
        after_ids = {a for link in comp for a in link.after_ids}
        befores = [fn for fn in before if fn.id in before_ids]
        afters = [fn for fn in after if fn.id in after_ids]
        matches.append(_component_match(len(matches), befores, afters, comp, ctx))

    linked_after = {a for link in links for a in link.after_ids}
    by_before = {fn.id: fn for fn in before}
    for fa in after:
        if fa.id in linked_after:
            continue
        rev = reverse.get(fa.id) or []
        if not rev:
            matches.append(
                _new_match(
                    len(matches),
                    fa,
                    True,
                    "lexical",
                    "Новая функция: у функции нет кандидатов среди «до» — обратный поиск по всем "
                    "функциям «до» не нашёл похожих.",
                )
            )
            continue
        top = by_before[rev[0].after_id]
        review = reviews.get(top.id)
        if review is not None and fa.id in review.presented:
            how = (
                "проверена моделью — связь с этой функцией не подтверждена"
                if review.how == "llm"
                else "дословно совпадает с другой функцией «после» и сопоставлена с ней"
            )
            matches.append(
                _new_match(
                    len(matches),
                    fa,
                    True,
                    "llm" if review.how == "llm" else "lexical",
                    f"Новая функция: пары среди «до» нет. Ближайшая функция «до» {_ref(top)} "
                    f"{how}.",
                )
            )
        else:
            matches.append(
                _new_match(
                    len(matches),
                    fa,
                    False,
                    "lexical",
                    f"Кандидат в новые — требует проверки: обратный поиск нашёл похожую функцию "
                    f"«до» {_ref(top)} ({top.id}), но проверка связи не состоялась.",
                )
            )
    return matches


def confirm_loss(
    fn: Function,
    after: list[Function],
    after_clauses: list[Clause] | None,
    llm: LLM | None,
    *,
    before_clauses: list[Clause] | None = None,
    unit_changes: list[UnitChange] | None = None,
) -> FunctionMatch:
    """Потеря — только после проверки по ВСЕМУ документу «после» (функции + сырые пункты).

    `lost = true` с пунктом из переданных → `status = lost, verified = True`. Во всех прочих
    случаях — кандидат в потери (`verified = False`) с причиной в `note`.
    """
    after = [fa for fa in after if fa.modality != "prohibition"]
    ctx = _Ctx.build(llm or LLM(), [fn], after, after_clauses, before_clauses, unit_changes)
    return _confirm_loss(0, fn, ctx)
