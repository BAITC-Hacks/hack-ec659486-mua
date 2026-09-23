"""P1: разбор .docx тестового комплекта (редакции 8 и 9) в пункты с контекстом."""

import re
import unicodedata
import zipfile
from pathlib import Path

import pytest

from app.parse import detect_modality, get_clause, parse_docx
from app.schemas import Document

DATA = Path(__file__).resolve().parents[2] / "data" / "case11"


def _docx(redaction: str) -> Path:
    for path in DATA.glob("*.docx"):
        if f"редакция_{redaction}_" in unicodedata.normalize("NFC", path.name):
            return path
    raise FileNotFoundError(f"нет редакции {redaction} в {DATA}")


@pytest.fixture(scope="module")
def doc8() -> Document:
    return parse_docx(_docx("8"), "before")


@pytest.fixture(scope="module")
def doc9() -> Document:
    return parse_docx(_docx("9"), "after")


@pytest.fixture(params=["8", "9"], scope="module")
def doc(request, doc8, doc9) -> Document:
    return doc8 if request.param == "8" else doc9


# --- Общие свойства обеих редакций ----------------------------------------------------------


def test_document_meta(doc8, doc9):
    assert doc8.version == "before" and doc9.version == "after"
    assert doc8.kind == doc9.kind == "polozhenie"
    assert doc8.name.endswith(".docx")
    assert re.fullmatch(r"[0-9a-f]{12}", doc8.id) and doc8.id != doc9.id
    # id стабилен: повторный разбор даёт тот же документ
    assert parse_docx(_docx("8"), "before") == doc8


def test_many_numbered_clauses(doc):
    assert sum(1 for c in doc.clauses if c.number) >= 300


def test_clause_1_4(doc):
    clause = get_clause(doc, "1.4")
    assert clause is not None and "Главный аудитор" in clause.text


def test_sections(doc):
    sections = {c.section for c in doc.clauses}
    assert any(s.startswith("3. Структура") for s in sections)
    assert doc.clauses[0].section == "Преамбула"
    # заголовки 10–14 склеены в docx с предыдущим абзацем — всё равно открывают раздел
    for num in ("10", "11", "12", "13", "14"):
        assert any(s.startswith(f"{num}. ") for s in sections), num


def test_toc_dropped(doc):
    for c in doc.clauses:
        page_tail = re.search(r"\s\d+$", c.text) and not re.search(r"[a-zа-яё]", c.text)
        assert not page_tail, c.text
        assert "ОГЛАВЛЕНИЕ 38" not in c.text
    assert not any(c.text.strip() == "Оглавление" for c in doc.clauses)


def test_indices_and_ids(doc):
    indices = [c.index for c in doc.clauses]
    assert indices == sorted(set(indices))
    ids = [c.id for c in doc.clauses]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(rf"{doc.id}:p\d+:\d+", i) for i in ids)


def test_section_path_never_empty(doc):
    assert all(c.section_path for c in doc.clauses)
    assert all(c.section_path[0] == c.section for c in doc.clauses)


def test_quotes_are_verbatim(doc):
    """Текст пункта — дословный фрагмент абзаца документа (без печатного номера)."""
    with zipfile.ZipFile(_docx("8" if doc.version == "before" else "9")) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    raw = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", xml.replace("</w:p>", " ")))
    raw = raw.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    missing = [c.text for c in doc.clauses if c.text not in raw]
    assert not missing, missing[:3]


def test_headings_neutral(doc):
    heading = next(c for c in doc.clauses if c.number == "5")
    assert heading.text == "Права и обязанности"
    assert heading.modality == "neutral"


def test_section_2_paths(doc):
    assert get_clause(doc, "2.3").section_path[0].startswith("2. Цели, задачи и функции")
    path = get_clause(doc, "2.4.1").section_path
    assert any(p.startswith("2.4.") for p in path)


def test_lead_in_unnumbered_heading(doc):
    clause = get_clause(doc, "5.1")
    assert clause.lead_in == "Главный аудитор:"
    assert clause.modality == "duty"


# --- Контекст: редакция 8 --------------------------------------------------------------------


def test_prohibition_context(doc8):
    clause = get_clause(doc8, "5.9.1")
    assert clause.modality == "prohibition"
    assert "не имеют права" in clause.lead_in
    assert clause.section_path == [
        "5. Права и обязанности",
        "5.9. Главный аудитор и работники БВА не имеют права:",
    ]


def test_right_context(doc8):
    clause = get_clause(doc8, "5.8.1")
    assert clause.modality == "right"
    assert clause.lead_in == "5.8. Работники БВА имеют право:"


def test_letter_subclause(doc8):
    clause = get_clause(doc8, "5.9.1.а")
    assert clause is not None
    assert clause.text.startswith("разрабатывать дизайн")
    assert "не имеют права" in clause.lead_in
    assert clause.modality == "prohibition"
    assert any(p.startswith("5.9.1.") for p in clause.section_path)
    assert get_clause(doc8, "5.9.1.а.") == clause


def test_paragraph_with_three_clauses(doc8):
    c9, c10, c11 = (get_clause(doc8, n) for n in ("3.9", "3.10", "3.11"))
    block = c9.id.rsplit(":", 1)[0]
    assert [c.id for c in (c9, c10, c11)] == [f"{block}:0", f"{block}:1", f"{block}:2"]
    assert c10.text.startswith("Работники могут выполнять")
    assert c11.text.startswith("По вопросам соблюдения")


def test_heading_split_by_toc(doc8):
    """«4. Внутренний аудит в ДЗО При взаимодействии …:» — заголовок + вводная для 4.1–4.4."""
    heading = get_clause(doc8, "4")
    assert heading.section == "4. Внутренний аудит в ДЗО"
    assert get_clause(doc8, "4.1").lead_in.startswith("При взаимодействии")


# --- Контекст: редакция 9 --------------------------------------------------------------------


def test_prohibition_context_after(doc9):
    under = [c for c in doc9.clauses if c.lead_in and "не имеют права" in c.lead_in]
    assert under and all(c.modality == "prohibition" for c in under)
    assert any(c.text.startswith("разрабатывать дизайн") for c in under)


def test_executor_lead_in_after(doc9):
    clause = get_clause(doc9, "5.3.1")
    assert clause.lead_in == "5.3. Директоры департаментов и Директоры направлений ДИТААД и ДОА:"


# --- Модальность и ошибки --------------------------------------------------------------------


def test_detect_modality():
    assert detect_modality("Работники не вправе") == "prohibition"
    assert detect_modality("БВА вправе запрашивать") == "right"
    assert detect_modality("обязан обеспечить …, а также имеет право:") == "right"
    assert detect_modality("функциональные обязанности") is None
    assert detect_modality("не несут ответственности") is None
    assert detect_modality("Главный аудитор несёт ответственность") == "duty"


@pytest.mark.parametrize("name", ["x.pdf", "x.xlsx", "x.txt"])
def test_unsupported_format(name):
    with pytest.raises(ValueError, match="не поддержан"):
        parse_docx(name, "before")


def test_broken_and_empty_docx(tmp_path):
    empty = tmp_path / "empty.docx"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="пуст"):
        parse_docx(empty, "before")
    broken = tmp_path / "broken.docx"
    broken.write_bytes(b"not a zip at all")
    with pytest.raises(ValueError, match="повреждён"):
        parse_docx(broken, "after")
