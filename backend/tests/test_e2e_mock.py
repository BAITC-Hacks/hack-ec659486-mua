"""S17: сценарий эксперта на настоящем контрольном комплекте без ключа OpenAI."""

import time
from collections.abc import Iterator
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.schemas import Report, RunStatus, Source


@pytest.fixture(scope="module")
def demo(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[TestClient, str, RunStatus, Report]]:
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("LLM_MODE", "mock")
        patch.setenv("RUNTIME_DIR", str(tmp_path_factory.mktemp("e2e-runtime")))
        patch.delenv("OPENAI_API_KEY", raising=False)
        get_settings.cache_clear()
        with TestClient(create_app()) as client:
            created = client.post("/api/runs/demo")
            assert created.status_code == 201, f"тестовый комплект не запустился: {created.text}"
            run_id = created.json()["run_id"]
            deadline = time.monotonic() + 90
            while True:
                response = client.get(f"/api/runs/{run_id}")
                assert response.status_code == 200, f"статус запуска недоступен: {response.text}"
                status = RunStatus.model_validate(response.json())
                if status.status in {"done", "partial", "error"}:
                    break
                if time.monotonic() >= deadline:
                    pytest.fail(f"тестовый комплект не завершился за 90 с: {response.text}")
                time.sleep(0.5)
            assert status.status != "error", f"ошибка анализа: {status.detail}"
            report_response = client.get(f"/api/runs/{run_id}/report")
            assert report_response.status_code == 200, (
                f"отчёт тестового комплекта недоступен: {report_response.text}"
            )
            report = Report.model_validate(report_response.json())
            yield client, run_id, status, report
        get_settings.cache_clear()


def _norm(value: str) -> str:
    return " ".join(value.split()).casefold()


def _check_source(client: TestClient, run_id: str, source: Source) -> None:
    assert source.quote.strip(), f"источник без цитаты: {source.model_dump()}"
    doc_id = quote(source.doc_id, safe="")
    address = source.clause_number or source.clause_id
    assert address, f"источник без адреса пункта: {source.model_dump()}"
    response = client.get(f"/api/runs/{run_id}/clauses/{doc_id}/{quote(address, safe='')}")
    assert response.status_code == 200, (
        f"пункт {source.doc_id}:{address} не открывается: {response.text}"
    )
    clause = response.json()
    assert clause["number"] == source.clause_number, (
        f"номер источника не совпадает: {source.doc_id}:{address}"
    )
    assert clause["id"] == source.clause_id, f"ID источника не совпадает: {source.doc_id}:{address}"
    assert _norm(source.quote)[:40] in _norm(clause["text"]), (
        f"цитата не найдена в пункте {source.doc_id}:{address}: {source.quote[:80]!r}"
    )


def _all_sources(report: Report) -> Iterator[tuple[str, list[Source]]]:
    for change in report.unit_changes:
        yield f"подразделение {change.id}", change.sources
        for unit in (change.unit_before, change.unit_after):
            if unit is not None:
                yield f"подразделение {unit.id}", unit.sources
    for match in report.function_matches:
        yield f"сопоставление {match.id}", match.sources
        for function in (*match.before, *match.after):
            yield f"функция {function.id}", function.sources
    for duplicate in report.duplicates:
        yield f"дубль {duplicate.id}, первая функция", duplicate.function_a.sources
        yield f"дубль {duplicate.id}, вторая функция", duplicate.function_b.sources
    for conflict in report.conflicts:
        yield f"конфликт {conflict.id}", conflict.sources
        for function in conflict.functions:
            yield f"конфликт {conflict.id}, функция {function.id}", function.sources


def test_demo_finds_changes_and_opens_real_sources(
    demo: tuple[TestClient, str, RunStatus, Report],
) -> None:
    client, run_id, status, report = demo
    assert report.run_id == run_id, "отчёт относится к другому запуску"
    assert any(c.status in {"transformed", "created"} for c in report.unit_changes), (
        "не найдена реорганизация или создание подразделения"
    )
    assert any(m.status == "lost" for m in report.function_matches), "не найдена потеря функции"
    assert report.duplicates, "не найдено дублирование функций"

    # Независимые опорные случаи из data/case11/diff-8-vs-9.md.
    changes_text = _norm(
        " ".join(
            unit.name
            for change in report.unit_changes
            for unit in (change.unit_before, change.unit_after)
            if unit is not None
        )
    )
    assert "дитаад" in changes_text, "в редакции 9 не найден ДИТААД (пункт 3.4а)"
    assert "доа" in changes_text, "в редакции 9 не найден ДОА (пункт 3.4б)"
    assert any(
        change.status == "transformed"
        and change.unit_before is not None
        and "направление внутреннего аудита" in _norm(change.unit_before.name)
        and any(
            "директор направления внутреннего аудита" in _norm(source.quote)
            for source in change.sources
        )
        for change in report.unit_changes
    ), "не показано преобразование директора направления внутреннего аудита"
    before_text = _norm(
        " ".join(
            f"{function.text} {' '.join(source.quote for source in function.sources)}"
            for match in report.function_matches
            for function in match.before
        )
    )
    assert "контроль устранения недостатков" in before_text, (
        "функция ред. 8 из пункта 3.6 не сопоставлена и не отмечена кандидатом в потери"
    )
    assert "разработке проектов документации" in before_text, (
        "функция ред. 8 из пункта 3.11/4.10 не сопоставлена и не отмечена кандидатом"
    )
    after_text = _norm(
        " ".join(function.text for match in report.function_matches for function in match.after)
    )
    assert "потенциальном конфликте при совмещении" in after_text, (
        "новая функция редакции 9 о потенциальном конфликте не показана"
    )

    assert "unverified_candidates" in report.stats, "в stats нет числа находок, требующих проверки"
    checked: set[tuple[str, str, str | None, str]] = set()
    for label, sources in _all_sources(report):
        assert sources, f"находка без источника: {label}"
        for source in sources:
            key = (source.doc_id, source.clause_id, source.clause_number, source.quote)
            if key not in checked:
                _check_source(client, run_id, source)
                checked.add(key)

    if status.status == "partial" and status.missing_steps == ["conclusion"]:
        pytest.xfail(f"ожидается фикстура S15 для заключения: {status.detail}")
    assert status.status == "done", (
        f"анализ не завершился полностью: {status.status}, "
        f"missing_steps={status.missing_steps}, detail={status.detail}"
    )
    assert report.conclusion_md.strip(), "аналитическое заключение пустое"
    assert "не сформировано" not in report.conclusion_md.casefold(), (
        "аналитическое заключение не сформировано"
    )


def test_report_markdown_contains_conclusion(
    demo: tuple[TestClient, str, RunStatus, Report],
) -> None:
    client, run_id, _, report = demo
    response = client.get(f"/api/runs/{run_id}/report.md")
    assert response.status_code == 200, f"экспорт Markdown недоступен: {response.text}"
    assert response.headers["content-type"].startswith("text/markdown"), (
        f"неверный тип экспорта: {response.headers['content-type']}"
    )
    assert report.conclusion_md in response.text, "экспорт не содержит текст заключения"
