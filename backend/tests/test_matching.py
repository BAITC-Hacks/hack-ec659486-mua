"""S10: гибридные кандидаты и проверка сопоставления функций до↔после (LLM_MODE=mock, без ключа).

Функции и пункты собраны руками по `schemas.py` (модуль функций S09 не нужен). Тексты пунктов —
дословно из тестового комплекта `data/case11` (редакции 8 и 9 Положения о внутреннем аудите),
кроме синтетической пары для известной коллизии сигнатуры «аудит ИТ» / «аудит закупок».
Фикстуры `mocks/verify_matches/`, `mocks/confirm_loss/` — в формате живого ответа модели.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Iterator

import numpy as np
import pytest

from app import candidates as cand_mod
from app import matching
from app.candidates import (
    Candidate,
    embed,
    find_candidates,
    find_duplicate_candidates,
    is_template,
    tokenize,
)
from app.config import get_settings
from app.llm import LLM, LLMError
from app.matching import confirm_loss, verify_matches
from app.prebuilt.lib_normalize import signature
from app.schemas import Clause, Function, FunctionMatch, Modality, Source, Unit, UnitChange

DOC8 = ("b3fc97c65ef0", "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx", "before")
DOC9 = ("486684e5cc24", "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx", "after")
SYN_B = ("syn-b", "Синтетический пример: коллизия сигнатуры (до)", "before")
SYN_A = ("syn-a", "Синтетический пример: коллизия сигнатуры (после)", "after")

SEC2 = "2. Цели, задачи и функции внутреннего аудита"
SEC5 = "5. Права и обязанности"
L_24 = (
    "2.4. Для решения поставленных задач и достижения целей внутренний аудит осуществляет "
    "следующие функции:"
)
L8_53 = "5.3. Директор направления внутреннего аудита:"
L8_56 = (
    "5.6. Директор ДККМ обязан обеспечить выполнение всех возложенных на ДККМ задач и функций "
    "в соответствии с данным Положением в зоне деятельности, а также имеет право:"
)
L9_53 = "5.3. Директоры департаментов и Директоры направлений ДИТААД и ДОА:"
L9_532 = (
    "5.3.2. организуют по решению Главного аудитора руководство курируемых плановых и "
    "внеплановых проверок:"
)
L9_56 = (
    "5.6. Директоры департаментов обязаны обеспечить выполнение всех возложенных задач и "
    "функций в соответствии с данным Положением в зоне деятельности, а также имеют право:"
)


def clause(
    doc: tuple[str, str, str],
    para: int,
    number: str,
    text: str,
    lead_in: str | None,
    path: list[str],
    modality: Modality = "duty",
) -> Clause:
    return Clause(
        id=f"{doc[0]}:p{para}:0",
        number=number,
        section=path[0] if path else None,
        section_path=path,
        text=text,
        index=para,
        lead_in=lead_in,
        modality=modality,
    )


def source(doc: tuple[str, str, str], cl: Clause) -> Source:
    return Source(
        doc_id=doc[0],
        doc_name=doc[1],
        version=doc[2],  # type: ignore[arg-type]
        clause_id=cl.id,
        clause_number=cl.number,
        quote=cl.text,
    )


def function(
    fid: str,
    doc: tuple[str, str, str],
    cl: Clause,
    text: str,
    unit_id: str | None,
    executor: str | None,
    *,
    modality: Modality | None = None,
    context: tuple[str, ...] = (),
) -> Function:
    return Function(
        id=fid,
        unit_id=unit_id,
        text=text,
        category="function",
        modality=modality or cl.modality,
        executor=executor,
        action=None,
        object=None,
        signature=signature(text),
        context_clause_numbers=list(context),
        sources=[source(doc, cl)],
    )


# --- Пункты тестового комплекта ------------------------------------------------------------------

C8_2415 = clause(
    DOC8,
    84,
    "2.4.15",
    "организация работы по повышению профессионального уровня работников БВА;",
    L_24,
    [SEC2, L_24],
)
C8_533 = clause(
    DOC8,
    152,
    "5.3.3",
    "организует по решению Главного аудитора руководство курируемых плановых и внеплановых "
    "проверок по Обществу, в том числе:",
    L8_53,
    [SEC5, L8_53],
)
C8_5311 = clause(
    DOC8,
    168,
    "5.3.11",
    "участвует в разработке проектов документации, регламентирующей работу БВА;",
    L8_53,
    [SEC5, L8_53],
    "neutral",
)
C8_563 = clause(
    DOC8,
    202,
    "5.6.3",
    "выносить предложения по объему и содержанию внешней оценки БВА Главному аудитору;",
    L8_56,
    [SEC5, L8_56],
    "right",
)
C8_565 = clause(
    DOC8,
    204,
    "5.6.5",
    "вести переписку с Руководителями Общества по вопросам, входящим в зону ответственности;",
    L8_56,
    [SEC5, L8_56],
    "right",
)
C9_2415 = clause(
    DOC9,
    83,
    "2.4.15",
    "организация работы по повышению профессионального уровня работников БВА;",
    L_24,
    [SEC2, L_24],
)
C9_532 = clause(
    DOC9,
    160,
    "5.3.2",
    "организуют по решению Главного аудитора руководство курируемых плановых и внеплановых "
    "проверок:",
    L9_53,
    [SEC5, L9_53],
)
C9_532A = clause(
    DOC9,
    161,
    "5.3.2.а",
    "аудит ИТ систем, Информационная безопасность, аудит персональных данных, ИТ-инциденты, "
    "непрерывность бизнеса, дата аналитика, применения языков программирования, создание "
    "дашбордов, автоматизация процессов ВА (ДИТААД);",
    f"{L9_53} {L9_532}",
    [SEC5, L9_53, L9_532],
)
C9_532B = clause(
    DOC9,
    162,
    "5.3.2.б",
    "аудит процессов развития, операционных и поддерживающих процессов Общества (ДОА).",
    f"{L9_53} {L9_532}",
    [SEC5, L9_53, L9_532],
)
C9_537 = clause(
    DOC9,
    177,
    "5.3.7",
    "организуют контроль устранения недостатков и нарушений, выявленных в ходе проведения "
    "проверок БВА, обеспечивают и совершенствуют работу системы мониторинга действий "
    "(корректирующих мер) Руководителей Общества, предпринимаемых по результатам внутренних "
    "аудитов и проектов.",
    L9_53,
    [SEC5, L9_53],
)
C9_5312 = clause(
    DOC9, 182, "5.3.12", "участвуют в разработке ВНД БВА;", L9_53, [SEC5, L9_53], "neutral"
)
C9_563 = clause(
    DOC9,
    209,
    "5.6.3",
    "вести переписку с Руководителями Общества по вопросам, входящим в зону ответственности;",
    L9_56,
    [SEC5, L9_56],
    "right",
)
C9_115 = clause(
    DOC9,
    453,
    "11.5",
    "Объем и содержание внешней оценки могут быть скорректированы по усмотрению Главного "
    "аудитора, с учетом рекомендаций Президента Общества или по решению Совета директоров, "
    "исходя из поставленных целей Общества.",
    None,
    ["11. Оценка деятельности внутреннего аудита"],
    "neutral",
)
BEFORE_CLAUSES = [C8_2415, C8_533, C8_5311, C8_563, C8_565]
AFTER_CLAUSES = [C9_2415, C9_532, C9_532A, C9_532B, C9_537, C9_5312, C9_563, C9_115]

# --- Подразделения (карта S05) -------------------------------------------------------------------

BVA8, DVA8, DKKM8 = (f"{DOC8[0]}:unit:{i}" for i in range(3))
BVA9, DITAAD9, DOA9, DKKM9 = (f"{DOC9[0]}:unit:{i}" for i in range(4))


def unit(uid: str, name: str, doc: tuple[str, str, str], cl: Clause) -> Unit:
    return Unit(id=uid, name=name, version=doc[2], parent=None, sources=[source(doc, cl)])  # type: ignore[arg-type]


def change(idx: int, before: Unit | None, after: Unit | None, status: str) -> UnitChange:
    return UnitChange(
        id=f"unit-change:{idx}",
        unit_before=before,
        unit_after=after,
        status=status,  # type: ignore[arg-type]
        note="",
        sources=(before.sources if before else []) + (after.sources if after else []),
    )


U_BVA8 = unit(BVA8, "Блок внутреннего аудита (БВА)", DOC8, C8_2415)
U_DVA8 = unit(DVA8, "Направление внутреннего аудита", DOC8, C8_533)
U_DKKM8 = unit(DKKM8, "Департамент контроля качества аудита и методологии (ДККМ)", DOC8, C8_565)
U_BVA9 = unit(BVA9, "Блок внутреннего аудита (БВА)", DOC9, C9_2415)
U_DITAAD9 = unit(DITAAD9, "Департамент ИТ-аудита и анализа данных (ДИТААД)", DOC9, C9_532A)
U_DOA9 = unit(DOA9, "Департамент операционного аудита (ДОА)", DOC9, C9_532B)
U_DKKM9 = unit(DKKM9, "Департамент контроля качества аудита и методологии (ДККМ)", DOC9, C9_563)
UNIT_CHANGES = [
    change(0, U_BVA8, U_BVA9, "kept"),
    change(1, U_DKKM8, U_DKKM9, "kept"),
    change(2, U_DVA8, U_DITAAD9, "transformed"),
    change(3, U_DVA8, U_DOA9, "transformed"),
]

# --- Функции основного сценария ------------------------------------------------------------------

F8_KEPT = function(
    "f8-2.4.15",
    DOC8,
    C8_2415,
    "организация работы по повышению профессионального уровня работников БВА",
    BVA8,
    "БВА",
)
F8_SPLIT = function(
    "f8-5.3.3",
    DOC8,
    C8_533,
    "организует по решению Главного аудитора руководство курируемых плановых и внеплановых "
    "проверок по Обществу",
    DVA8,
    "Директор направления внутреннего аудита",
)
F8_CHANGED = function(
    "f8-5.3.11",
    DOC8,
    C8_5311,
    "участвует в разработке проектов документации, регламентирующей работу БВА",
    DVA8,
    "Директор направления внутреннего аудита",
)
F8_LOST = function(
    "f8-5.6.3",
    DOC8,
    C8_563,
    "выносить предложения по объему и содержанию внешней оценки БВА Главному аудитору",
    DKKM8,
    "Директор ДККМ",
)
F8_MOVED = function(
    "f8-5.6.5",
    DOC8,
    C8_565,
    "вести переписку с Руководителями Общества по вопросам, входящим в зону ответственности",
    DKKM8,
    "Директор ДККМ",
)
F9_KEPT = function(
    "f9-2.4.15",
    DOC9,
    C9_2415,
    "организация работы по повышению профессионального уровня работников БВА",
    BVA9,
    "БВА",
)
F9_SPLIT_A = function(
    "f9-5.3.2.а",
    DOC9,
    C9_532A,
    "организуют по решению Главного аудитора руководство курируемых плановых и внеплановых "
    "проверок по направлениям: аудит ИТ систем, информационная безопасность, аудит персональных "
    "данных, ИТ-инциденты, непрерывность бизнеса (ДИТААД)",
    DITAAD9,
    "Директор ДИТААД",
    context=("5.3.2",),
)
F9_SPLIT_B = function(
    "f9-5.3.2.б",
    DOC9,
    C9_532B,
    "организуют по решению Главного аудитора руководство курируемых плановых и внеплановых "
    "проверок по направлению: аудит процессов развития, операционных и поддерживающих процессов "
    "Общества (ДОА)",
    DOA9,
    "Директор ДОА",
    context=("5.3.2",),
)
F9_CHANGED = function(
    "f9-5.3.12",
    DOC9,
    C9_5312,
    "участвуют в разработке ВНД БВА",
    DITAAD9,
    "Директоры департаментов и Директоры направлений ДИТААД и ДОА",
)
F9_MOVED = function(
    "f9-5.6.3",
    DOC9,
    C9_563,
    "вести переписку с Руководителями Общества по вопросам, входящим в зону ответственности",
    BVA9,
    "Директоры департаментов",
)
F9_NEW = function(
    "f9-5.3.7",
    DOC9,
    C9_537,
    "обеспечивают и совершенствуют работу системы мониторинга действий (корректирующих мер) "
    "Руководителей Общества, предпринимаемых по результатам внутренних аудитов и проектов",
    BVA9,
    "Директоры департаментов и Директоры направлений ДИТААД и ДОА",
)
BEFORE = [F8_KEPT, F8_SPLIT, F8_CHANGED, F8_LOST, F8_MOVED]
AFTER = [F9_KEPT, F9_SPLIT_A, F9_SPLIT_B, F9_CHANGED, F9_MOVED, F9_NEW]
GHOST_ID = "f9-ghost-99.9"  # чужой id в фикстуре verify_matches для F8_CHANGED

# --- Синтетическая коллизия сигнатуры ------------------------------------------------------------

S_B = clause(
    SYN_B, 1, "2.3", "проводит аудит, в том числе ИТ-систем Общества;", None, ["2. Функции"]
)
S_A = clause(SYN_A, 1, "2.3", "проводит аудит, в том числе закупок Общества;", None, ["2. Функции"])
FS_IT = function(
    "syn-b-2.3", SYN_B, S_B, "проводит аудит, в том числе ИТ-систем Общества", "u-b", "БВА"
)
FS_PROC = function(
    "syn-a-2.3", SYN_A, S_A, "проводит аудит, в том числе закупок Общества", "u-a", "БВА"
)


# --- Инфраструктура ------------------------------------------------------------------------------


@pytest.fixture
def llm(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[LLM]:
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(cand_mod, "EMBEDDINGS_DIR", tmp_path / "embeddings")
    get_settings.cache_clear()
    yield LLM(get_settings())
    get_settings.cache_clear()


def run_main(llm: LLM) -> list[FunctionMatch]:
    cands = find_candidates(BEFORE, AFTER, llm)
    return verify_matches(
        BEFORE,
        AFTER,
        cands,
        llm,
        AFTER_CLAUSES,
        before_clauses=BEFORE_CLAUSES,
        unit_changes=UNIT_CHANGES,
    )


def run_collision(llm: LLM) -> list[FunctionMatch]:
    return verify_matches([FS_IT], [FS_PROC], find_candidates([FS_IT], [FS_PROC], llm), llm, [S_A])


def match_of(matches: list[FunctionMatch], fn: Function) -> FunctionMatch:
    found = [m for m in matches if fn.id in {f.id for f in m.before + m.after}]
    assert len(found) == 1, f"{fn.id}: {len(found)} сопоставлений"
    return found[0]


def assert_partition(matches: list[FunctionMatch], before, after) -> None:
    """Каждая функция «до» и «после» — ровно в одном FunctionMatch, источники есть."""
    seen_before = [f.id for m in matches for f in m.before]
    seen_after = [f.id for m in matches for f in m.after]
    assert sorted(seen_before) == sorted(f.id for f in before)
    assert sorted(seen_after) == sorted(f.id for f in after)
    for m in matches:
        assert m.sources
        side = m.before or m.after
        assert {s.clause_id for f in side for s in f.sources} <= {s.clause_id for s in m.sources}
        assert 0.0 <= m.confidence <= 1.0
    assert len({m.id for m in matches}) == len(matches)


# --- (а) коллизия сигнатуры ----------------------------------------------------------------------


def test_signature_collision_is_candidate_not_decision(llm: LLM) -> None:
    assert FS_IT.signature == FS_PROC.signature  # известная коллизия lib_normalize.signature
    cands = find_candidates([FS_IT], [FS_PROC], llm)[FS_IT.id]
    assert [c.after_id for c in cands] == [FS_PROC.id]
    assert "signature" in cands[0].reasons and "exact" not in cands[0].reasons

    matches = run_collision(llm)
    assert_partition(matches, [FS_IT], [FS_PROC])
    lost = match_of(matches, FS_IT)
    assert lost.status == "lost" and lost.after == []
    assert lost.status not in ("kept", "changed")
    # фикстура verify_matches — none, фикстуры confirm_loss нет → не проверено
    assert lost.verified is False
    assert "нет ответа проверки" in lost.note
    assert "совпадения нет" in lost.note
    new = match_of(matches, FS_PROC)
    assert new.status == "new" and new.verified is True and new.verification == "llm"


# --- (б) split ------------------------------------------------------------------------------------


def test_split_one_before_to_two_after(llm: LLM) -> None:
    m = match_of(run_main(llm), F8_SPLIT)
    assert m.kind == "split" and m.status == "changed"
    assert [f.id for f in m.after] == [F9_SPLIT_A.id, F9_SPLIT_B.id]
    assert len(m.after) == 2 and m.before == [F8_SPLIT]
    assert m.verified is True and m.verification == "llm" and m.confidence == 0.8
    assert "назначение: передано преобразованному подразделению" in m.note
    assert {s.clause_number for s in m.sources} == {"5.3.3", "5.3.2.а", "5.3.2.б"}


# --- (в) потеря только после confirm_loss ---------------------------------------------------------


def test_loss_verified_only_with_confirm_loss(llm: LLM) -> None:
    m = match_of(run_main(llm), F8_LOST)
    assert m.status == "lost" and m.after == [] and m.kind == "one_to_one"
    assert m.verified is True and m.verification == "llm" and m.confidence == 0.85
    assert "11.5" in m.note and "Объем и содержание внешней оценки" in m.note


def test_loss_without_fixture_stays_candidate(llm: LLM) -> None:
    m = confirm_loss(F8_LOST, [F9_KEPT], [C9_115], llm)
    assert m.status == "lost" and m.verified is False and m.verification == "lexical"
    assert m.confidence == 0.4
    assert "требует проверки" in m.note and "нет ответа проверки" in m.note
    assert m.sources == F8_LOST.sources


# --- (г) точное совпадение


def test_exact_text_same_owner_is_kept_exact(llm: LLM) -> None:
    m = match_of(run_main(llm), F8_KEPT)
    assert m.status == "kept" and m.kind == "one_to_one"
    assert m.after == [F9_KEPT]
    assert m.verified is True and m.verification == "exact" and m.confidence == 1.0
    assert "содержание: сохранено; назначение: сохранено" in m.note


def test_exact_text_other_unit_is_moved(llm: LLM) -> None:
    m = match_of(run_main(llm), F8_MOVED)
    assert m.status == "moved" and m.after == [F9_MOVED]
    assert m.verification == "exact" and m.verified is True
    assert "содержание: сохранено; назначение: перенесено" in m.note
    assert "ДККМ" in m.note and "БВА" in m.note


def test_exact_text_other_modality_is_not_auto_kept(llm: LLM) -> None:
    after = F9_KEPT.model_copy(update={"modality": "right"})
    matches = verify_matches([F8_KEPT], [after], None, llm, [C9_2415])
    assert_partition(matches, [F8_KEPT], [after])
    m = match_of(matches, F8_KEPT)
    assert not (m.status == "kept" and m.verified)
    assert m.verified is False  # фикстуры нет → проверка не состоялась


# --- (д) выдуманные id и номера пунктов -----------------------------------------------------------


def test_foreign_after_id_is_dropped(llm: LLM, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="app.matching"):
        m = match_of(run_main(llm), F8_CHANGED)
    assert m.status == "changed" and m.kind == "one_to_one"
    assert [f.id for f in m.after] == [F9_CHANGED.id]
    assert GHOST_ID not in {f.id for f in m.after}
    assert m.verified is True and m.verification == "llm"
    assert "назначение: передано преобразованному подразделению" in m.note
    assert any(GHOST_ID in r.getMessage() for r in caplog.records)


def test_nearest_clause_not_passed_is_invalid(llm: LLM) -> None:
    m = confirm_loss(F8_LOST, [], [C9_115, C9_563], llm)
    assert m.status == "lost" and m.verified is False
    assert "невалиден" in m.note and "7.7" in m.note


# --- (е) кандидаты


def test_tokenize_keeps_codes_and_abbreviations() -> None:
    tokens = tokenize("Директор ДККМ согласует план работ БВА и ДЗО по п. 2.3. (ИТ-аудит СВА)")
    for token in ("дккм", "бва", "дзо", "2.3", "ит", "сва"):
        assert token in tokens
    assert "и" not in tokens and "по" not in tokens
    assert tokenize("проверок")[0] == tokenize("проверки")[0]


def test_find_candidates_top5_and_no_dense_in_mock(llm: LLM) -> None:
    assert embed([F8_KEPT.text, F9_KEPT.text], llm) == [None, None]
    extra = [
        function(
            f"f9-extra-{i}",
            DOC9,
            C9_537,
            f"контролирует работу БВА по направлению {i}",
            BVA9,
            "БВА",
        )
        for i in range(6)
    ]
    result = find_candidates(BEFORE, AFTER + extra, llm)
    assert set(result) == {f.id for f in BEFORE}
    for items in result.values():
        assert 1 <= len(items) <= 5
        assert all(isinstance(c, Candidate) and c.reasons for c in items)
        assert all(set(c.reasons) <= {"exact", "lexical", "signature", "dense"} for c in items)
        assert "dense" not in {r for c in items for r in c.reasons}
    first = result[F8_KEPT.id][0]
    assert first.after_id == F9_KEPT.id and first.reasons == ["exact"] and math.isinf(first.score)
    assert find_candidates([], AFTER, llm) == {}
    assert find_candidates(BEFORE, [], llm) == {f.id: [] for f in BEFORE}


def test_dense_rank_from_cache(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Вектор из кэша участвует в RRF как ранг `dense`, но не решает ничего сам."""
    monkeypatch.setattr(cand_mod, "EMBEDDINGS_DIR", tmp_path)
    texts = {
        F8_LOST.text: [1.0, 0.0, 0.0],
        F9_NEW.text: [0.9, 0.1, 0.0],
        F9_KEPT.text: [0.0, 1.0, 0.0],
    }
    for text, vector in texts.items():
        sha = cand_mod._sha256(text)
        payload = {"model": "text-embedding-3-small", "text_sha256": sha, "vector": vector}
        (tmp_path / f"{sha}.json").write_text(json.dumps(payload), encoding="utf-8")
    vectors = embed([F8_LOST.text, "нет в кэше"], None)
    assert isinstance(vectors[0], np.ndarray) and vectors[1] is None
    items = find_candidates([F8_LOST], [F9_NEW, F9_KEPT], None)[F8_LOST.id]
    by_id = {c.after_id: c for c in items}
    assert by_id[F9_NEW.id].reasons == ["dense"]  # лексика не нашла — dense добавил кандидата
    assert by_id[F9_KEPT.id].reasons == ["lexical", "dense"]  # два ранга → выше по RRF
    assert items[0].after_id == F9_KEPT.id


# --- (ж) полнота, пустые входы, дубли, лимит ------------------------------------------------------


def test_every_function_in_exactly_one_match(llm: LLM) -> None:
    matches = run_main(llm)
    assert_partition(matches, BEFORE, AFTER)
    new = match_of(matches, F9_NEW)
    assert new.status == "new" and new.before == [] and new.kind == "one_to_one"
    assert new.verified is True
    for m in matches:
        if m.status == "lost":
            assert m.after == [] and len(m.before) == 1
        if m.status == "new":
            assert m.before == [] and len(m.after) == 1


def test_empty_inputs_do_not_call_llm(llm: LLM, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("LLM не должен вызываться")

    monkeypatch.setattr(matching, "_call_llm", forbidden)
    assert verify_matches([], [], {}, llm, []) == []
    assert verify_matches([], [], None, llm) == []
    prohibition = F8_KEPT.model_copy(update={"id": "f8-ban", "modality": "prohibition"})
    assert verify_matches([prohibition], [], {}, llm, []) == []
    only_new = verify_matches([], [F9_NEW], {}, llm, AFTER_CLAUSES)
    assert [m.status for m in only_new] == ["new"] and only_new[0].verified is True


def test_empty_candidates_go_straight_to_confirm_loss(
    llm: LLM, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def spy(_llm, name, _payload, _model):
        calls.append(name)
        raise LLMError("нет фикстуры (тест)")

    monkeypatch.setattr(matching, "_call_llm", spy)
    matches = verify_matches([F8_LOST], [], {F8_LOST.id: []}, llm, [C9_115])
    assert calls == ["confirm_loss"]
    assert [(m.status, m.verified) for m in matches] == [("lost", False)]


def test_call_limit_leaves_candidates_unverified(llm: LLM, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(matching, "MAX_VERIFY_CALLS", 0)
    matches = run_main(llm)
    assert_partition(matches, BEFORE, AFTER)
    for fn in (F8_SPLIT, F8_CHANGED, F8_LOST):
        m = match_of(matches, fn)
        assert m.status == "lost" and m.verified is False and "лимит пакета" in m.note
    assert match_of(matches, F8_KEPT).verified is True  # точное совпадение решает код


def test_duplicate_candidates_skip_same_unit_and_templates() -> None:
    same_text = (
        "вести переписку с Руководителями Общества по вопросам, входящим в зону ответственности"
    )
    dkkm = function("d-dkkm", DOC9, C9_563, same_text, DKKM9, "Директор ДККМ")
    ditaad = function("d-ditaad", DOC9, C9_563, same_text, DITAAD9, "Директор ДИТААД")
    ditaad_twin = function("d-ditaad-2", DOC9, C9_563, same_text, DITAAD9, "Директор ДИТААД")
    other1 = function("d-other-1", DOC9, C9_5312, "выполняет иные функции", DOA9, "Директор ДОА")
    other2 = function("d-other-2", DOC9, C9_5312, "выполняет иные функции", DKKM9, "Директор ДККМ")
    orders = [
        function(
            f"d-order-{u}",
            DOC9,
            C9_5312,
            "осуществляет выполнение прочих поручений Главного аудитора",
            u,
            None,
        )
        for u in (DOA9, BVA9)
    ]
    assert is_template(other1.text) and is_template(orders[0].text)
    pairs = find_duplicate_candidates([dkkm, ditaad, ditaad_twin, other1, other2, *orders])
    assert pairs, "одинаковая функция у двух подразделений должна стать кандидатом"
    for a, b, similarity in pairs:
        assert a.unit_id != b.unit_id
        assert 0.0 <= similarity <= 1.0
        assert not ({a.id, b.id} & {other1.id, other2.id, *(o.id for o in orders)})
    ids = {frozenset((a.id, b.id)) for a, b, _ in pairs}
    assert frozenset((dkkm.id, ditaad.id)) in ids
    assert frozenset((ditaad.id, ditaad_twin.id)) not in ids
    top = next(p for p in pairs if {p[0].id, p[1].id} == {dkkm.id, ditaad.id})
    assert top[2] == 1.0
