"""P5 «Дубли и конфликты интересов» (S11): кандидаты, verify_duplicates, узкие правила
конфликтов, explain_conflict, mock-фикстуры по хэшу входа.

Функции собираются вручную по `schemas.py`. Пункты и цитаты с номерами из редакции 9
(`data/case11/Положение_о_внутреннем_аудите_редакция_9_обезличено.docx`) — дословные тексты
пунктов. Сценарии, которых в тестовом комплекте нет (акт инвентаризации, закупки у аудита),
собраны в синтетическом документе `Синтетический_пример.docx` с пунктами «9.*».
Кандидаты дублей передаются через `candidate_pairs`, поэтому тест не зависит от `app.candidates`.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

import pytest

import app.duplicates as duplicates
import app.rules.conflicts as conflicts
from app.config import Settings
from app.duplicates import VerifyDuplicatesOut, find_duplicates, is_template, verify_payload
from app.llm import LLM, MOCKS_DIR, LLMError
from app.rules import (
    call_llm,
    clean_clause_refs,
    control_strength,
    mock_fixture_path,
    object_overlap,
)
from app.rules.conflicts import ExplainConflictOut, find_conflicts, is_excluded
from app.schemas import Conflict, Duplicate, Function, Source

DOC_ID = "486684e5cc24"
DOC_NAME = "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx"
SYN_ID = "synthetic"
SYN_NAME = "Синтетический_пример.docx"

LEAD_53 = "Директоры департаментов и Директоры направлений ДИТААД и ДОА:"
LEAD_54 = "Директор департамента непрерывного мониторинга системы внутреннего контроля:"
LEAD_55 = "Директор департамента контроля качества аудита и методологии (далее Директор ДККМ):"
LEAD_58 = "Главный аудитор и работники БВА не имеют права:"
LEAD_51 = (
    "Организует работу БВА, осуществляя общее руководство и распределение обязанностей между "
    "работниками БВА, инициирует и проводит совещания для обсуждения вопросов, относящихся к "
    "компетенции БВА:"
)

# Дословные тексты пунктов редакции 9.
T_538 = (
    "анализируют результаты проверок БВА и непрерывного аудита, готовят материалы и предложения "
    "в зоне ответственности для представления Главному аудитору;"
)
T_545 = (
    "анализирует результаты непрерывного аудита и готовит материалы и предложения в зоне "
    "ответственности для представления Главному аудитору;"
)
T_532A = (
    "аудит ИТ систем, Информационная безопасность, аудит персональных данных, ИТ-инциденты, "
    "непрерывность бизнеса, дата аналитика, применения языков программирования, создание "
    "дашбордов, автоматизация процессов ВА (ДИТААД);"
)
T_532B = "аудит процессов развития, операционных и поддерживающих процессов Общества (ДОА)."
T_516 = (
    "представляет отчеты об итогах выполнения плана работы БВА на ежеквартальной основе и по "
    "итогам года в соответствии с требованиями настоящего Положения;"
)
T_553 = (
    "готовит отчеты об итогах выполнения плана работы БВА в соответствии с требованиями "
    "настоящего Положения;"
)
T_514 = (
    "организует контроль устранения недостатков и нарушений, выявленных в ходе проведения проверок;"
)
T_537 = (
    "организуют контроль устранения недостатков и нарушений, выявленных в ходе проведения "
    "проверок БВА, обеспечивают и совершенствуют работу системы мониторинга действий "
    "(корректирующих мер) Руководителей Общества, предпринимаемых по результатам внутренних "
    "аудитов и проектов."
)
T_5312 = "участвуют в разработке ВНД БВА;"
T_549 = "участвует в разработке ВНД БВА;"
T_554 = (
    "разрабатывает методические материалы, актуализирует ВНД, регламентирующие деятельность "
    "внутреннего аудита (единая методология внутреннего аудита);"
)
T_5313 = "осуществляют выполнение прочих поручений Главного аудитора."
T_5410 = "осуществляет выполнение прочих поручений Главного аудитора."
T_2421 = (
    "взаимодействие с подразделениями Общества по вопросам, относящимся к деятельности "
    "внутреннего аудита, и другие функции, необходимые для решения задач, поставленных перед "
    "внутренним аудитом в Обществе."
)
T_581 = (
    "выполнять функциональные обязанности, не связанные с деятельностью внутреннего аудита, как "
    "это определено в настоящем Положении, в том числе:"
)
T_581D = "инициировать и утверждать транзакции, не относящиеся непосредственно к деятельности БВА."
T_583 = (
    "подписывать от имени Общества платежные (расчетные) и бухгалтерские документы, а также иные "
    "документы, в соответствии с которыми Общество принимает риски, либо визировать такие "
    "документы, за исключением документов, инициируемых в связи с исполнением бюджета затрат БВА;"
)
T_5110 = (
    "организует контроль качества внутреннего аудита в порядке, предусмотренном настоящим "
    "Положением, назначает работников, ответственных за взаимодействие с внешним экспертом "
    "(группой экспертов);"
)

UNIT_NAMES = {
    "u-bva": "Блок внутреннего аудита (БВА)",
    "u-ditaad": "Департамент ИТ-аудита и анализа данных (ДИТААД)",
    "u-doa": "Департамент операционного аудита (ДОА)",
    "u-dnm": "Департамент непрерывного мониторинга системы внутреннего контроля (ДНМ)",
    "u-dkkm": "Департамент контроля качества аудита и методологии (ДККМ)",
}


def src(number: str, text: str, *, doc: str = DOC_ID, name: str = DOC_NAME) -> Source:
    return Source(
        doc_id=doc,
        doc_name=name,
        version="after",
        clause_id=f"{doc}:{number}",
        clause_number=number,
        quote=text,
    )


def fn(
    fid: str,
    unit: str | None,
    number: str,
    text: str,
    *,
    executor: str | None,
    modality: str = "duty",
    lead: tuple[str, str] | None = None,
    signature: str | None = None,
    synthetic: bool = False,
) -> Function:
    doc = {"doc": SYN_ID, "name": SYN_NAME} if synthetic else {}
    sources = [src(number, text, **doc)]
    if lead is not None:
        sources.append(src(lead[0], lead[1], **doc))
    return Function(
        id=fid,
        unit_id=unit,
        text=text,
        category="function",
        modality=modality,  # type: ignore[arg-type]
        executor=executor,
        action=None,
        object=None,
        signature=signature,
        context_clause_numbers=[lead[0]] if lead else [],
        sources=sources,
    )


# --- функции тестового комплекта (редакция 9) -------------------------------------------------

F_538 = fn(
    "f-5.3.8", "u-ditaad", "5.3.8", T_538, executor="Директоры ДИТААД и ДОА", lead=("5.3", LEAD_53)
)
F_545 = fn("f-5.4.5", "u-dnm", "5.4.5", T_545, executor="Директор ДНМ", lead=("5.4", LEAD_54))
F_532A = fn(
    "f-5.3.2.а",
    "u-ditaad",
    "5.3.2.а",
    T_532A,
    executor="Директоры ДИТААД",
    lead=("5.3", LEAD_53),
    signature="КОНТРОЛИРОВАТЬ|аудит",
)
F_532B = fn(
    "f-5.3.2.б",
    "u-doa",
    "5.3.2.б",
    T_532B,
    executor="Директоры ДОА",
    lead=("5.3", LEAD_53),
    signature="КОНТРОЛИРОВАТЬ|аудит",
)
F_516 = fn("f-5.1.6", "u-bva", "5.1.6", T_516, executor="Главный аудитор", lead=("5.1", LEAD_51))
F_553 = fn("f-5.5.3", "u-dkkm", "5.5.3", T_553, executor="Директор ДККМ", lead=("5.5", LEAD_55))
F_514 = fn("f-5.1.4", "u-bva", "5.1.4", T_514, executor="Главный аудитор", lead=("5.1", LEAD_51))
F_537 = fn(
    "f-5.3.7", "u-ditaad", "5.3.7", T_537, executor="Директоры ДИТААД и ДОА", lead=("5.3", LEAD_53)
)
F_5312 = fn(
    "f-5.3.12",
    "u-ditaad",
    "5.3.12",
    T_5312,
    executor="Директоры ДИТААД и ДОА",
    lead=("5.3", LEAD_53),
)
F_549 = fn("f-5.4.9", "u-dnm", "5.4.9", T_549, executor="Директор ДНМ", lead=("5.4", LEAD_54))
F_554 = fn("f-5.5.4", "u-dkkm", "5.5.4", T_554, executor="Директор ДККМ", lead=("5.5", LEAD_55))
F_5313 = fn(
    "f-5.3.13",
    "u-ditaad",
    "5.3.13",
    T_5313,
    executor="Директоры ДИТААД и ДОА",
    lead=("5.3", LEAD_53),
)
F_5410 = fn("f-5.4.10", "u-dnm", "5.4.10", T_5410, executor="Директор ДНМ", lead=("5.4", LEAD_54))
F_5110 = fn(
    "f-5.1.10", "u-bva", "5.1.10", T_5110, executor="Главный аудитор", lead=("5.1", LEAD_51)
)
C_581 = fn(
    "c-5.8.1",
    "u-bva",
    "5.8.1",
    T_581,
    executor="Главный аудитор и работники БВА",
    modality="prohibition",
    lead=("5.8", LEAD_58),
)
C_583 = fn(
    "c-5.8.3",
    "u-bva",
    "5.8.3",
    T_583,
    executor="Главный аудитор и работники БВА",
    modality="prohibition",
    lead=("5.8", LEAD_58),
)

# --- синтетические сценарии (в тестовом комплекте таких пунктов нет) ------------------------

S_ACT_MAKE = fn(
    "s-9.1",
    "u-ahd",
    "9.1",
    "составляет акт инвентаризации имущества",
    executor="Административно-хозяйственный отдел",
    synthetic=True,
)
S_ACT_APPROVE = fn(
    "s-9.2",
    "u-ahd",
    "9.2",
    "утверждает акт инвентаризации имущества",
    executor="Административно-хозяйственный отдел",
    synthetic=True,
)
S_ACT_AGREE = fn(
    "s-9.3",
    "u-ahd",
    "9.3",
    "согласовывает акт инвентаризации имущества",
    executor="Административно-хозяйственный отдел",
    synthetic=True,
)
S_ACT_PARTICIPATE = fn(
    "s-9.4",
    "u-ahd",
    "9.4",
    "участие в контроле составления акта инвентаризации имущества",
    executor="Административно-хозяйственный отдел",
    synthetic=True,
)
S_STAFF_APPROVE = fn(
    "s-9.5",
    "u-ahd",
    "9.5",
    "утверждает штатное расписание отдела",
    executor="Административно-хозяйственный отдел",
    synthetic=True,
)
S_PLAN_MAKE = fn(
    "s-9.6",
    "u-bva",
    "9.6",
    "формирует годовой план аудита",
    executor="Блок внутреннего аудита",
    synthetic=True,
)
S_PLAN_APPROVE = fn(
    "s-9.7",
    "u-bva",
    "9.7",
    "утверждает годовой план аудита",
    executor="Блок внутреннего аудита",
    synthetic=True,
)
S_PURCHASE = fn(
    "s-9.8",
    "u-bva",
    "9.8",
    "осуществляет закупки товаров и услуг для нужд Общества",
    executor="Блок внутреннего аудита",
    synthetic=True,
)
S_SIGN_PAYMENTS = fn(
    "s-9.9",
    "u-bva",
    "9.9",
    "подписывает платежные документы Общества",
    executor="Главный аудитор",
    synthetic=True,
)
S_OTHER_A = fn(
    "s-9.10",
    "u-ahd",
    "9.10",
    "выполняет иные функции по поручению руководства",
    executor="Административно-хозяйственный отдел",
    synthetic=True,
)
S_OTHER_B = fn(
    "s-9.11",
    "u-fin",
    "9.11",
    "выполняет иные функции по поручению руководства",
    executor="Финансовый отдел",
    synthetic=True,
)


# --- фикстуры pytest ------------------------------------------------------------------------------


@pytest.fixture
def llm(monkeypatch: pytest.MonkeyPatch) -> LLM:
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return LLM(Settings(llm_mode="mock", openai_api_key=None))


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Счётчик LLM-вызовов обоих модулей (имя вызова на каждый вызов)."""
    made: list[str] = []

    def counting(real: Any) -> Any:
        def wrapper(llm: LLM, name: str, payload: dict[str, Any], model: Any) -> Any:
            made.append(name)
            return real(llm, name, payload, model)

        return wrapper

    monkeypatch.setattr(duplicates, "call_llm", counting(duplicates.call_llm))
    monkeypatch.setattr(conflicts, "call_llm", counting(conflicts.call_llm))
    return made


def by_unit(*functions: Function) -> dict[str, list[Function]]:
    grouped: dict[str, list[Function]] = {}
    for f in functions:
        grouped.setdefault(f.unit_id or "", []).append(f)
    return grouped


def assert_sourced(item: Duplicate | Conflict) -> None:
    if isinstance(item, Duplicate):
        assert item.function_a.sources and item.function_b.sources
    else:
        assert item.sources
        numbers = {s.clause_number for s in item.sources}
        for f in item.functions:
            assert f.sources[0].clause_number in numbers


# --- дубли --------------------------------------------------------------------------------------


def test_duplicate_same_action_same_object_verified(llm: LLM, calls: list[str]) -> None:
    result = find_duplicates(by_unit(F_538, F_545), llm, [(F_538, F_545, 0.82)])
    assert len(result) == 1
    dup = result[0]
    assert dup.verified is True
    assert dup.function_a.id == "f-5.3.8" and dup.function_b.id == "f-5.4.5"
    assert dup.similarity == pytest.approx(0.82)
    assert "Проверка: llm" in dup.note
    assert "непрерывного аудита" in dup.verification_note
    assert dup.id == "dup-1"
    assert_sourced(dup)
    assert calls == ["verify_duplicates"]


def test_same_signature_but_llm_says_not_duplicate(llm: LLM, calls: list[str]) -> None:
    assert F_532A.signature == F_532B.signature  # известная коллизия «аудит ИТ» / «аудит …»
    assert find_duplicates(by_unit(F_532A, F_532B), llm, [(F_532A, F_532B, 0.9)]) == []
    assert calls == ["verify_duplicates"]


def test_participation_on_one_side_is_not_duplicate(llm: LLM, calls: list[str]) -> None:
    functions = by_unit(F_5312, F_549, F_554)
    pairs = [(F_5312, F_554, 0.5), (F_5312, F_549, 1.0)]
    assert find_duplicates(functions, llm, pairs) == []
    assert calls == []  # участие отсекается кодом, LLM не нужна


def test_template_phrases_give_no_candidates(llm: LLM, calls: list[str]) -> None:
    assert is_template(T_5313) and is_template(T_2421) and is_template(S_OTHER_A.text)
    assert not is_template(T_538)
    functions = by_unit(F_5313, F_5410, S_OTHER_A, S_OTHER_B)
    pairs = [(F_5313, F_5410, 1.0), (S_OTHER_A, S_OTHER_B, 1.0)]
    assert find_duplicates(functions, llm, pairs) == []
    assert calls == []


def test_same_unit_is_never_compared(llm: LLM, calls: list[str]) -> None:
    twin = F_538.model_copy(update={"id": "f-5.3.8-copy"})
    assert find_duplicates(by_unit(F_538, twin), llm, [(F_538, twin, 1.0)]) == []
    assert calls == []


def test_prohibitions_are_not_duplicates(llm: LLM, calls: list[str]) -> None:
    a = fn("c-a", "u-ditaad", "5.8.1.д", T_581D, executor="работники БВА", modality="prohibition")
    b = fn("c-b", "u-dnm", "5.8.1.д", T_581D, executor="работники БВА", modality="prohibition")
    assert find_duplicates(by_unit(a, b), llm, [(a, b, 1.0)]) == []
    assert calls == []


def test_inconsistent_llm_answer_stays_unverified(llm: LLM) -> None:
    # фикстура: is_duplicate=true, но both_executors=false — ответ невалиден
    result = find_duplicates(by_unit(F_516, F_553), llm, [(F_516, F_553, 0.7)])
    assert len(result) == 1
    dup = result[0]
    assert dup.verified is False
    assert dup.verification_note.startswith("требует проверки: ответ проверки противоречив")
    assert "both_executors=false" in dup.verification_note
    assert "Проверка: lexical" in dup.note
    assert_sourced(dup)


def test_missing_fixture_keeps_candidate_unverified(llm: LLM) -> None:
    path = mock_fixture_path("verify_duplicates", verify_payload(F_514, F_537))
    assert not path.exists()
    with pytest.raises(LLMError, match=path.name):
        call_llm(llm, "verify_duplicates", verify_payload(F_514, F_537), VerifyDuplicatesOut)
    result = find_duplicates(by_unit(F_514, F_537), llm, [(F_514, F_537, 0.6)])
    assert [d.verified for d in result] == [False]
    assert result[0].verification_note.startswith("требует проверки: нет ответа проверки")
    assert path.name in result[0].verification_note


def test_verified_duplicates_come_first(llm: LLM) -> None:
    functions = by_unit(F_514, F_537, F_538, F_545)
    result = find_duplicates(functions, llm, [(F_514, F_537, 0.6), (F_538, F_545, 0.8)])
    assert [d.verified for d in result] == [True, False]
    assert [d.id for d in result] == ["dup-1", "dup-2"]


def test_call_limit_leaves_pairs_unverified(
    llm: LLM, calls: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(duplicates, "MAX_DUPLICATE_CALLS", 0)
    result = find_duplicates(by_unit(F_538, F_545), llm, [(F_538, F_545, 0.8)])
    assert [d.verified for d in result] == [False]
    assert "лимит" in result[0].verification_note
    assert calls == []


def test_fallback_signature_candidates_without_candidates_module(
    llm: LLM, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setitem(sys.modules, "app.candidates", None)  # import → ImportError
    same = "ПРОЧЕЕ|результаты непрерывного аудита"
    a = F_538.model_copy(update={"signature": same})
    b = F_545.model_copy(update={"signature": same})
    other = F_553.model_copy(update={"signature": "СОЗДАВАТЬ|отчеты итогах"})
    with caplog.at_level(logging.WARNING, logger="app.duplicates"):
        result = find_duplicates(by_unit(a, b, other), llm)
    assert "app.candidates недоступен, кандидаты только по сигнатуре" in caplog.text
    assert len(result) == 1 and result[0].verified is True
    assert "равенство сигнатуры" in result[0].note


# --- конфликты интересов ------------------------------------------------------------------------


def test_weak_control_is_not_a_conflict(llm: LLM, calls: list[str]) -> None:
    assert control_strength(S_ACT_AGREE.text) == "weak"
    assert find_conflicts(by_unit(S_ACT_MAKE, S_ACT_AGREE), llm) == []
    assert calls == []


def test_own_annual_audit_plan_is_not_a_conflict(llm: LLM, calls: list[str]) -> None:
    assert control_strength(S_PLAN_APPROVE.text) == "strong"
    assert object_overlap(S_PLAN_MAKE, S_PLAN_APPROVE) == 1.0
    reason = is_excluded((S_PLAN_MAKE, S_PLAN_APPROVE))
    assert reason is not None and "планирование" in reason
    assert find_conflicts(by_unit(S_PLAN_MAKE, S_PLAN_APPROVE), llm) == []
    assert calls == []


def test_participation_in_control_is_excluded(llm: LLM, calls: list[str]) -> None:
    reason = is_excluded((S_ACT_MAKE, S_ACT_PARTICIPATE))
    assert reason is not None and "участие" in reason
    assert find_conflicts(by_unit(S_ACT_MAKE, S_ACT_PARTICIPATE), llm) == []
    assert calls == []


def test_different_objects_give_no_pair(llm: LLM, calls: list[str]) -> None:
    assert object_overlap(S_ACT_MAKE, S_STAFF_APPROVE) == 0.0
    assert find_conflicts(by_unit(S_ACT_MAKE, S_STAFF_APPROVE), llm) == []
    assert calls == []


@pytest.mark.parametrize(
    ("text", "reason_part"),
    [
        ("направляет акт инвентаризации имущества на утверждение", "направляет на согласование"),
        ("организация и контроль инвентаризации имущества", "организация и контроль"),
        ("контролирует исполнение договоров подрядчиками", "чужим исполнением"),
        ("оказывает содействие в инвентаризации имущества", "участие"),
        ("руководствуется актом инвентаризации имущества", "ссылается на документ"),
        ("регистрирует акт проверки имущества", "названия документа"),
    ],
)
def test_exclusions(text: str, reason_part: str) -> None:
    other = fn("s-x", "u-ahd", "9.99", text, executor=None, synthetic=True)
    reason = is_excluded((S_ACT_MAKE, other))
    assert reason is not None and reason_part in reason


def test_real_clauses_management_and_different_objects_are_not_conflicts(
    llm: LLM, calls: list[str]
) -> None:
    # 5.3.4 «организуют работу проектных команд» + 5.3.5.б «контроль качества работы проектной
    # команды» — управленческий оборот «организация и контроль», разнесённый по подпунктам
    t_534 = (
        "организуют работу проектных команд в зоне ответственности в соответствии с планом работ "
        "БВА и внутренними нормативными документами Общества, обеспечивая:"
    )
    t_535b = "контроль качества работы проектной команды;"
    organize = fn(
        "f-5.3.4",
        "u-ditaad",
        "5.3.4",
        t_534,
        executor="Директоры ДИТААД и ДОА",
        lead=("5.3", LEAD_53),
    )
    control = fn(
        "f-5.3.5.б",
        "u-ditaad",
        "5.3.5.б",
        t_535b,
        executor="Директоры ДИТААД и ДОА",
        lead=("5.3.5", "проводят проверки и обеспечивают выполнение плана работ БВА в том числе:"),
    )
    reason = is_excluded((organize, control))
    assert reason is not None and "организация и контроль" in reason
    # 2.4.2 «проведение внутренних аудиторских проверок» и 5.1.10 «контроль качества внутреннего
    # аудита»: общие прилагательные «внутренний/аудит» — ещё не один объект
    t_242 = (
        "проведение внутренних аудиторских проверок (далее - проверок) на основании утвержденного "
        "плана работ внутреннего аудита;"
    )
    audits = fn("f-2.4.2", "u-bva", "2.4.2", t_242, executor="БВА")
    assert object_overlap(audits, F_5110) < conflicts.OBJECT_OVERLAP_MIN
    assert find_conflicts(by_unit(organize, control, audits), llm) == []
    assert calls == []


def test_executes_and_approves_same_act_is_conflict_a(llm: LLM, calls: list[str]) -> None:
    result = find_conflicts(by_unit(S_ACT_MAKE, S_ACT_APPROVE), llm)
    assert len(result) == 1
    conflict = result[0]
    assert conflict.rule_id == "a"
    assert conflict.role_pattern == "исполнитель+контролёр"
    assert conflict.verified is True
    assert conflict.severity == "high"
    assert conflict.units == ["u-ahd"]
    assert [f.id for f in conflict.functions] == ["s-9.1", "s-9.2"]
    assert {s.clause_number for s in conflict.sources} == {"9.1", "9.2"}
    assert conflict.id == "conflict-1"
    # фикстура ссылается на п. 5.1.2, которого нет среди переданных, — ссылка удалена
    assert "5.1.2" not in conflict.explanation
    assert "п. 9.1" in conflict.explanation and "п. 9.2" in conflict.explanation
    assert_sourced(conflict)
    assert calls == ["explain_conflict"]


def test_audit_unit_doing_purchases_is_rule_c_unverified_without_fixture(llm: LLM) -> None:
    result = find_conflicts(by_unit(S_PURCHASE), llm, [C_581])
    assert len(result) == 1
    conflict = result[0]
    assert conflict.rule_id == "c"
    assert conflict.role_pattern == "аудитор+оператор"
    # фикстуры нет: LLMError внутри, снаружи — кандидат «требует проверки» с причиной
    assert conflict.verified is False
    assert conflict.verification_note.startswith("требует проверки: объяснение не получено")
    assert "mocks/explain_conflict/" in conflict.verification_note
    assert "осуществляет закупки товаров и услуг" in conflict.explanation  # цитата кодом
    assert [f.id for f in conflict.functions] == ["s-9.8", "c-5.8.1"]  # запрет-мандат — контекст
    assert {s.clause_number for s in conflict.sources} >= {"9.8", "5.8.1"}
    assert conflict.severity == "high"


def test_prohibition_gives_neither_conflict_nor_duplicate(llm: LLM, calls: list[str]) -> None:
    banned = fn(
        "c-5.8.1.д",
        "u-bva",
        "5.8.1.д",
        T_581D,
        executor="Главный аудитор и работники БВА",
        modality="prohibition",
        lead=("5.8.1", T_581),
    )
    assert find_conflicts(by_unit(banned), llm) == []
    assert find_conflicts({"u-bva": []}, llm, [banned]) == []
    assert calls == []
    # тот же текст как обязанность — уже «инициирует и утверждает» (правило b)
    duty = banned.model_copy(update={"id": "d-5.8.1.д", "modality": "duty"})
    result = find_conflicts(by_unit(duty), llm)
    assert [(c.rule_id, c.role_pattern) for c in result] == [("b", "инициатор+утверждающий")]


def test_violated_prohibition_is_conflict_e(llm: LLM) -> None:
    result = find_conflicts(by_unit(S_SIGN_PAYMENTS), llm, [C_583])
    assert len(result) == 1
    conflict = result[0]
    assert conflict.rule_id == "e"
    assert conflict.role_pattern == "запрет+исполнение"
    assert conflict.verified is True
    assert [f.id for f in conflict.functions] == ["s-9.9", "c-5.8.3"]
    assert {s.clause_number for s in conflict.sources} >= {"9.9", "5.8.3"}
    assert_sourced(conflict)


def test_self_control_verified_false_by_model_is_candidate(llm: LLM) -> None:
    result = find_conflicts(by_unit(F_5110), llm, unit_names=UNIT_NAMES)
    assert [c.rule_id for c in result] == ["d"]
    conflict = result[0]
    assert conflict.role_pattern == "самоконтроль"
    assert conflict.verified is False  # модель сомневается — «требует проверки»
    assert conflict.verification_note.startswith("требует проверки: ")
    assert "внешн" in conflict.verification_note
    assert conflict.severity == "low"


def test_empty_input_calls_no_llm(llm: LLM, calls: list[str]) -> None:
    assert find_duplicates({}, llm) == []
    assert find_duplicates({"u-bva": []}, llm, []) == []
    assert find_conflicts({}, llm) == []
    assert find_conflicts({"u-bva": []}, llm, []) == []
    assert calls == []


# --- номера пунктов и фикстуры --------------------------------------------------------------------


def test_clean_clause_refs_removes_unknown_numbers() -> None:
    text, removed = clean_clause_refs(
        "Совмещение по п. 9.1 и п. 9.2 (см. также п. 5.1.2); доля 0.85, 3 подразделения.",
        {"9.1", "9.2"},
    )
    assert removed == ["5.1.2"]
    assert "5.1.2" not in text
    assert "п. 9.1" in text and "п. 9.2" in text and "0.85" in text and "3 подразделения" in text


def test_fixtures_have_live_answer_format() -> None:
    models = {"verify_duplicates": VerifyDuplicatesOut, "explain_conflict": ExplainConflictOut}
    for name, model in models.items():
        files = sorted(Path(MOCKS_DIR, name).glob("*.json"))
        assert files, f"нет фикстур mocks/{name}"
        for path in files:
            model.model_validate(json.loads(path.read_text(encoding="utf-8")))
