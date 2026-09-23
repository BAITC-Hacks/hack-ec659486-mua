"""P1: разбор .docx в пункты с контекстом (детерминированно, без LLM).

Источник — `word/document.xml`, разбор через ElementTree в порядке блоков тела:
`w:p` (абзацы; стиль заголовка берётся из `word/styles.xml`), `w:tbl` (строки таблицы →
пункт «ячейка | ячейка» без номера), `w:sdt` (содержимое раскрывается). Если XML не
читается, запасной путь — `app.prebuilt.lib_docx.para_objs` (плоские абзацы без стилей).

Что делает разбор:
- номер пункта по началу абзаца (`1.`, `1.2.`, `1.2.3.`), буквенные подпункты (`а.`) —
  номер родителя + буква (`5.9.1.а`);
- абзац с несколькими пунктами подряд («3.9. … 3.10.Работники … 3.11.По …») делится на пункты,
  если внутренний номер — продолжение текущего (3.9 → 3.10 / 3.9.1 / 4);
- заголовок раздела — пункт первого уровня с коротким текстом или стилем «Заголовок 1»;
  если заголовок склеен с текстом, граница берётся из оглавления документа;
- оглавление («1. ОБЩИЕ ПОЛОЖЕНИЯ 1») в пункты не попадает;
- контекст пункта: `section_path` (раздел + родители по номеру), `lead_in` (вводные фразы,
  оканчивающиеся двоеточием, или короткий подзаголовок вида «Главный аудитор:»),
  `modality` (словари ниже).

`Clause.text` — текст пункта без печатного номера, дословно как в документе (пробелы
схлопнуты); номер — в `Clause.number`. `Clause.id` — адрес блока `{doc_id}:p{абзац}:{k}`
(`{doc_id}:t{таблица}:r{строка}` для таблиц), от печатного номера не зависит.
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.schemas import Clause, Document, DocumentKind, Modality, Version

logger = logging.getLogger(__name__)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

SUPPORTED_SUFFIX = ".docx"
PREAMBLE = "Преамбула"
SECTION_PATH_MAX = 200  # длина элемента section_path
HEADING_MAX = 120  # длина текста заголовка раздела
LEAD_IN_HEADING_MAX = 80  # короткий подзаголовок-вводная без двоеточия («Этапы проверки»)

# --- Словари модальности (переиспользует S09 для перепроверки Function.modality) -----------

PROHIBITION_MARKERS: tuple[str, ...] = (
    "не вправе",
    "не имеет права",
    "не имеют права",
    "запрещается",
    "не допускается",
)
RIGHT_MARKERS: tuple[str, ...] = ("имеет право", "имеют право", "вправе")
DUTY_MARKERS: tuple[str, ...] = (
    "осуществляет",
    "осуществляют",
    "обеспечивает",
    "обеспечивают",
    "проводит",
    "проводят",
    "формирует",
    "формируют",
    "представляет",
    "представляют",
    "организует",
    "организуют",
    "обязан",
    "обязана",
    "обязаны",
    "несёт ответственность",
    "несут ответственность",
)

# Начало пункта, который открывает нового исполнителя («Директор ДНМ:», «Работники БВА …»):
# такой пункт с двоеточием завершает действие предыдущей вводной без номера.
ROLE_START = re.compile(
    r"^(?:главн|директор|руководител|начальник|заместител|работник|сотрудник|менеджер|"
    r"специалист|департамент|отдел|управлени|служб|блок|сектор|групп|центр|бва\b)",
    re.IGNORECASE,
)


def _fold(text: str) -> str:
    """Нормализация для сравнения: регистр, ё→е, пробелы."""
    return re.sub(r"\s+", " ", text.casefold().replace("ё", "е")).strip()


def _marker_re(markers: tuple[str, ...]) -> re.Pattern[str]:
    alts = "|".join(re.escape(_fold(m)) for m in sorted(markers, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alts})(?!\w)")


# (модальность, шаблон, приоритет при совпадении конца: «не вправе» сильнее «вправе»)
_MODALITY_RES: tuple[tuple[Modality, re.Pattern[str], int], ...] = (
    ("prohibition", _marker_re(PROHIBITION_MARKERS), 2),
    ("right", _marker_re(RIGHT_MARKERS), 1),
    ("duty", _marker_re(DUTY_MARKERS), 0),
)


def detect_modality(text: str | None) -> Modality | None:
    """Явный маркер модальности в тексте; при нескольких — последний по тексту.

    «…обязан обеспечить …, а также имеет право:» → right (маркер перед двоеточием управляет
    перечнем). Нет маркера — None.
    """
    if not text:
        return None
    folded = _fold(text)
    best: tuple[int, int, Modality] | None = None
    for modality, pattern, priority in _MODALITY_RES:
        for match in pattern.finditer(folded):
            key = (match.end(), priority, modality)
            if best is None or key[:2] > best[:2]:
                best = key
    return best[2] if best else None


def lead_in_modality(lead_in: str | None) -> Modality | None:
    """Модальность вводной: запрет в любой части цепочки вводных действует на весь перечень."""
    if not lead_in:
        return None
    if _MODALITY_RES[0][1].search(_fold(lead_in)):
        return "prohibition"
    return detect_modality(lead_in)


def clause_modality(text: str, lead_in: str | None) -> Modality:
    """Собственный явный маркер пункта важнее вводной; иначе вводная; иначе neutral."""
    return detect_modality(text) or lead_in_modality(lead_in) or "neutral"


# --- Низкий уровень: блоки документа -------------------------------------------------------


@dataclass
class _Block:
    text: str
    address: str  # "p12" или "t0:r3"
    style_level: int | None = None  # 1 — «Заголовок 1» и т.п.
    is_table_row: bool = False
    is_toc: bool = False


def _paragraph_text(p: ET.Element) -> str:
    parts: list[str] = []
    for el in p.iter():
        if el.tag == f"{W}t":
            parts.append(el.text or "")
        elif el.tag in (f"{W}tab", f"{W}br", f"{W}cr"):
            parts.append(" ")
        elif el.tag == f"{W}noBreakHyphen":
            parts.append("-")
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _read_styles(z: zipfile.ZipFile) -> dict[str, tuple[int | None, bool]]:
    """styleId → (уровень заголовка, стиль оглавления)."""
    try:
        root = ET.fromstring(z.read("word/styles.xml"))
    except (KeyError, ET.ParseError):
        return {}
    styles: dict[str, tuple[int | None, bool]] = {}
    for st in root.iter(f"{W}style"):
        if st.get(f"{W}type") not in (None, "paragraph"):
            continue
        sid = st.get(f"{W}styleId") or ""
        name_el = st.find(f"{W}name")
        name = name_el.get(f"{W}val", "") if name_el is not None else ""
        level: int | None = None
        outline = st.find(f"{W}pPr/{W}outlineLvl")
        if outline is not None and (outline.get(f"{W}val") or "").isdigit():
            lvl = int(outline.get(f"{W}val") or "9")
            level = lvl + 1 if lvl < 9 else None
        if level is None:
            m = re.search(r"(?:heading|заголовок)\s*(\d)", f"{name} {sid}", re.IGNORECASE)
            level = int(m.group(1)) if m else None
        is_toc = bool(re.match(r"(?:toc|оглавление)", name, re.IGNORECASE)) or "TOC" in sid
        styles[sid] = (level, is_toc)
    return styles


def _paragraph_style(p: ET.Element, styles: dict[str, tuple[int | None, bool]]):
    ppr = p.find(f"{W}pPr")
    if ppr is None:
        return None, False
    outline = ppr.find(f"{W}outlineLvl")
    if outline is not None and (outline.get(f"{W}val") or "").isdigit():
        lvl = int(outline.get(f"{W}val") or "9")
        if lvl < 9:
            return lvl + 1, False
    pstyle = ppr.find(f"{W}pStyle")
    if pstyle is None:
        return None, False
    return styles.get(pstyle.get(f"{W}val") or "", (None, False))


def _read_blocks(path: Path) -> list[_Block]:
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml")
            styles = _read_styles(z)
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise ValueError(
            f"файл пуст, повреждён или не является документом Word (.docx): {path.name}"
        ) from exc
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        logger.warning("document.xml не разобран, запасной путь lib_docx: %s", path.name)
        from app.prebuilt.lib_docx import para_objs

        return [_Block(o["text"], f"p{i}") for i, o in enumerate(para_objs(path))]

    body = root.find(f"{W}body")
    if body is None:
        raise ValueError(f"в документе нет тела word/document.xml: {path.name}")

    blocks: list[_Block] = []
    counters = {"p": 0, "t": 0}

    def add_paragraph(p: ET.Element) -> None:
        idx = counters["p"]
        counters["p"] += 1
        text = _paragraph_text(p)
        if text:
            level, is_toc = _paragraph_style(p, styles)
            blocks.append(_Block(text, f"p{idx}", style_level=level, is_toc=is_toc))

    def add_table(tbl: ET.Element) -> None:
        t = counters["t"]
        counters["t"] += 1
        rows = tbl.findall(f"{W}tr")
        # Таблица-макет в одну колонку (весь текст документа внутри ячейки) — это абзацы.
        if rows and all(len(tr.findall(f"{W}tc")) == 1 for tr in rows):
            for tr in rows:
                for tc in tr.findall(f"{W}tc"):
                    walk(tc)
            return
        for r, tr in enumerate(rows):
            cells = []
            for tc in tr.findall(f"{W}tc"):
                text = " ".join(filter(None, (_paragraph_text(p) for p in tc.iter(f"{W}p"))))
                if text:
                    cells.append(text)
            if cells:
                blocks.append(_Block(" | ".join(cells), f"t{t}:r{r}", is_table_row=True))

    def walk(container: ET.Element) -> None:
        for el in container:
            if el.tag == f"{W}p":
                add_paragraph(el)
            elif el.tag == f"{W}tbl":
                add_table(el)
            elif el.tag == f"{W}sdt":
                content = el.find(f"{W}sdtContent")
                if content is not None:
                    walk(content)

    walk(body)
    return blocks


# --- Номера пунктов ------------------------------------------------------------------------

_NUM_START = re.compile(r"^(\d{1,3}(?:\.\d{1,3})*)\.(?=\s|$|[«\"(A-ZА-ЯЁ])\s*")
_NUM_START_NODOT = re.compile(r"^(\d{1,3}(?:\.\d{1,3})+)\s+(?=\S)")
_LETTER_START = re.compile(r"^([а-яё])[.)]\s+(?=\S)")
_EMBEDDED = re.compile(r"(?<=[.;:!?»)])\s+(\d{1,3}(?:\.\d{1,3})*)\.\s*(?=[«\"A-ZА-ЯЁ])")
_TOC_TITLE = re.compile(r"^(\d{1,3})\.\s*(.+?)\s+\d{1,4}(?=\s|$)")
_TOC_MARKERS = {"оглавление", "содержание"}


def _leading_number(text: str) -> tuple[str | None, str]:
    """('3.2.1', тело) для «3.2.1. Тело»; (None, text) без номера."""
    m = _NUM_START.match(text) or _NUM_START_NODOT.match(text)
    if m:
        return m.group(1), text[m.end() :].strip()
    return None, text


def _successors(number: str) -> set[str]:
    """Номера, которыми может продолжиться пункт: 3.9 → {3.10, 3.9.1, 4}."""
    segs = [int(s) for s in number.split(".") if s.isdigit()]
    if not segs:
        return set()
    out = {".".join(map(str, segs[:k] + [segs[k] + 1])) for k in range(len(segs))}
    out.add(".".join(map(str, segs)) + ".1")
    return out


def _split_pieces(text: str, context_number: str | None) -> list[str]:
    """Делит абзац на пункты по внутренним номерам-продолжениям."""
    lead, _ = _leading_number(text)
    current = lead or context_number
    cuts: list[int] = []
    for m in _EMBEDDED.finditer(text):
        num = m.group(1)
        if current and num in _successors(current):
            cuts.append(m.start(1))
            current = num
    if not cuts:
        return [text]
    bounds = [0, *cuts, len(text)]
    return [
        text[a:b].strip() for a, b in zip(bounds, bounds[1:], strict=False) if text[a:b].strip()
    ]


def _is_toc_line(number: str | None, body: str, seen_sections: set[str]) -> bool:
    """Строка оглавления: «1. ОБЩИЕ ПОЛОЖЕНИЯ 1» (заглавные + номер страницы) или
    «3. Структура … 8» после уже пройденного раздела 3."""
    if number is None or not re.search(r"\s\d{1,4}$", body):
        return False
    if not re.search(r"[a-zа-яё]", body):
        return True
    return "." not in number and number in seen_sections and len(body) <= 150


def _toc_titles(blocks: list[_Block]) -> dict[str, str]:
    """Номер раздела → заголовок из оглавления (для отделения заголовка от склеенного текста)."""
    titles: dict[str, str] = {}
    for b in blocks:
        if re.search(r"[a-zа-яё]", b.text) or not re.search(r"\d$", b.text):
            continue
        m = _TOC_TITLE.match(b.text)
        if m and m.group(1) not in titles:
            titles[m.group(1)] = m.group(2).strip()
    return titles


# --- Разбор --------------------------------------------------------------------------------


@dataclass
class _Info:
    label: str  # «5.9. Главный аудитор и работники БВА не имеют права:»
    colon: bool
    is_heading: bool
    section: str
    cover: str | None  # вводная без номера, действующая на пункт


@dataclass
class _Letters:
    root: str  # номер пункта-родителя
    base: str  # номер, к которому приклеивается буква (родитель или вложенный подпункт)
    last: str
    last_number: str
    last_colon: bool


def _kind_by_name(name: str) -> DocumentKind:
    low = name.casefold()
    if "положение" in low:
        return "polozhenie"
    if "должностн" in low:
        return "di"
    if "приказ" in low:
        return "order"
    return "other"


def _parent(number: str) -> str | None:
    return number.rsplit(".", 1)[0] if "." in number else None


def _ancestors(number: str) -> list[str]:
    segs = number.split(".")
    return [".".join(segs[:k]) for k in range(1, len(segs))]


class _Parser:
    def __init__(self, doc_id: str, blocks: list[_Block]):
        self.doc_id = doc_id
        self.blocks = blocks
        self.toc = _toc_titles(blocks)
        self.clauses: list[Clause] = []
        self.section = PREAMBLE
        self.seen_sections: set[str] = set()
        self.by_number: dict[str, _Info] = {}
        self.last_numbered: str | None = None
        self.letters: _Letters | None = None
        self.u_text: str | None = None  # вводная без номера («Главный аудитор:»)
        self.u_level: int | None = None
        self.bullet_parent: str | None = None  # пункт с «:», которому подчинены абзацы-маркеры
        self.per_block: dict[str, int] = {}

    # -- служебное

    def _emit(self, block: _Block, number, text, section_path, lead_in, modality) -> None:
        k = self.per_block.get(block.address, 0)
        self.per_block[block.address] = k + 1
        cid = f"{self.doc_id}:{block.address}" + ("" if block.is_table_row else f":{k}")
        self.clauses.append(
            Clause(
                id=cid,
                number=number,
                section=self.section,
                section_path=section_path,
                text=text,
                index=len(self.clauses),
                lead_in=lead_in,
                modality=modality,
            )
        )

    def _open_section(self, title: str, number: str | None) -> None:
        self.section = title
        if number:
            self.seen_sections.add(number)
        self.u_text = self.u_level = None
        self.bullet_parent = None
        self.letters = None

    def _path_for(self, number: str) -> list[str]:
        path = [self.section]
        for anc in _ancestors(number):
            info = self.by_number.get(anc)
            if info and not info.is_heading and info.section == self.section:
                path.append(info.label[:SECTION_PATH_MAX])
        return path

    def _lead_in_for(self, number: str, own_cover: str | None) -> str | None:
        parts: list[str] = []
        outer: _Info | None = None
        cur = number
        while (pnum := _parent(cur)) is not None:
            info = self.by_number.get(pnum)
            if not info or info.is_heading or not info.colon or info.section != self.section:
                break
            parts.append(info.label)
            outer = info
            cur = pnum
        parts.reverse()
        cover = outer.cover if outer else own_cover
        joined = " ".join(([cover] if cover else []) + parts)
        return joined or None

    def _cover_numbered(self, level: int, body: str) -> str | None:
        """Действует ли вводная без номера на пункт уровня level; обновляет её состояние."""
        if self.u_text is None:
            return None
        if self.u_level is None:
            self.u_level = level
            return self.u_text
        opens_subject = detect_modality(body) is not None or bool(ROLE_START.match(body))
        if level < self.u_level or (level == self.u_level and body.endswith(":") and opens_subject):
            self.u_text = self.u_level = None
            return None
        return self.u_text

    # -- основной цикл

    def run(self) -> list[Clause]:
        for block in self.blocks:
            if block.is_toc or _fold(block.text).strip(" .:") in _TOC_MARKERS:
                continue
            if block.is_table_row:
                self._emit(block, None, block.text, [self.section], None, "neutral")
                continue
            for piece in _split_pieces(block.text, self.last_numbered):
                self._piece(block, piece)
        return self.clauses

    def _piece(self, block: _Block, text: str) -> None:
        number, body = _leading_number(text)
        if number is not None:
            if _is_toc_line(number, body, self.seen_sections):
                return
            if "." not in number and self._try_heading(block, number, body):
                return
            self._numbered(block, number, body)
            return
        m = _LETTER_START.match(text)
        if m and self.last_numbered is not None:
            self._lettered(block, m.group(1), text[m.end() :].strip())
            return
        if block.style_level == 1 and len(text) <= HEADING_MAX:
            self._open_section(text, None)
            self._emit(block, None, text, [self.section], None, "neutral")
            return
        self._unnumbered(block, text)

    def _try_heading(self, block: _Block, number: str, body: str) -> bool:
        if number in self.seen_sections or not body:
            return False
        title, rest = body, ""
        toc_title = self.toc.get(number)
        if toc_title and _fold(body).startswith(_fold(toc_title)):
            cut = len(toc_title)
            if cut == len(body) or body[cut] == " ":
                title, rest = body[:cut].strip(), body[cut:].strip()
        is_heading = (
            block.style_level == 1
            or title != body
            or (toc_title is not None and _fold(body) == _fold(toc_title))
            or (
                len(body) <= HEADING_MAX
                and (body[-1] not in ".;:," or body.isupper())
                and not body.endswith(":")
            )
        )
        if not is_heading:
            return False
        section_title = f"{number}. {title}"
        self._open_section(section_title, number)
        self.by_number[number] = _Info(section_title, False, True, section_title, None)
        self.last_numbered = number
        self._emit(block, number, title, [section_title], None, "neutral")
        if rest:
            self._unnumbered(block, rest)
        return True

    def _numbered(self, block: _Block, number: str, body: str) -> None:
        level = number.count(".") + 1
        cover = self._cover_numbered(level, body)
        lead_in = self._lead_in_for(number, cover)
        colon = body.endswith(":")
        label = f"{number}. {body}"
        self._emit(
            block, number, body, self._path_for(number), lead_in, clause_modality(body, lead_in)
        )
        self.by_number[number] = _Info(label, colon, False, self.section, cover)
        self.last_numbered = number
        self.letters = None
        self.bullet_parent = number if colon else None

    def _lettered(self, block: _Block, letter: str, body: str) -> None:
        root = self.last_numbered or ""
        st = self.letters
        if st is None or st.root != root:
            base = root
        elif letter > st.last:
            base = st.base
        elif st.last_colon:
            base = st.last_number  # «г. …информацию:» → «а.» вложен в г
        else:
            base = root  # буквы начались заново без вводной — номер может повториться
        number = f"{base}.{letter}"
        level = number.count(".") + 1
        cover = self._cover_numbered(level, body)
        lead_in = self._lead_in_for(number, cover)
        colon = body.endswith(":")
        self._emit(
            block, number, body, self._path_for(number), lead_in, clause_modality(body, lead_in)
        )
        self.by_number[number] = _Info(f"{letter}. {body}", colon, False, self.section, cover)
        self.letters = _Letters(root, base, letter, number, colon)
        if colon:
            self.bullet_parent = number

    def _unnumbered(self, block: _Block, text: str) -> None:
        # Вводная: «…:» или короткий подзаголовок без точки («Порядок назначения …»).
        # «Подготовительный этап.» — заголовок этапа, а не вводная к перечню.
        is_lead_in = text.endswith(":") or (
            block.style_level is not None
            and block.style_level >= 2
            and len(text) <= LEAD_IN_HEADING_MAX
            and text[-1] not in ".;,"
        )
        if self.bullet_parent and not is_lead_in:
            parent = self.bullet_parent
            info = self.by_number[parent]
            chain = self._lead_in_for(parent, info.cover)
            lead_in = " ".join(filter(None, (chain, info.label))) or None
            path = [*self._path_for(parent), info.label[:SECTION_PATH_MAX]]
            self._emit(block, None, text, path, lead_in, clause_modality(text, lead_in))
            return
        lead_in = None if is_lead_in else self.u_text
        self._emit(block, None, text, [self.section], lead_in, clause_modality(text, lead_in))
        if is_lead_in:
            self.u_text, self.u_level = text, None
            self.bullet_parent = None


# --- Публичный API -------------------------------------------------------------------------


def parse_docx(path: str | Path, version: Version, name: str | None = None) -> Document:
    """.docx → Document с пунктами. Не .docx, пустой или битый файл → ValueError."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix != SUPPORTED_SUFFIX:
        raise ValueError(f"формат не поддержан в прототипе: {suffix or 'без расширения'}")
    if version not in ("before", "after"):
        raise ValueError(f"версия документа должна быть before или after, получено: {version}")
    if not path.is_file():
        raise ValueError(f"файл не найден: {path.name}")
    content = path.read_bytes()
    if not content:
        raise ValueError(f"файл пуст: {path.name}")
    doc_id = hashlib.sha1(content).hexdigest()[:12]
    blocks = _read_blocks(path)
    clauses = _Parser(doc_id, blocks).run()
    if not clauses:
        raise ValueError(f"в документе не найдено текста: {path.name}")
    doc_name = name or unicodedata.normalize("NFC", path.name)
    return Document(
        id=doc_id, name=doc_name, version=version, kind=_kind_by_name(doc_name), clauses=clauses
    )


_LATIN_TO_CYR = str.maketrans("aeopcxyABEKMHOPCTX", "аеорсхуАВЕКМНОРСТХ")


def get_clause(doc: Document, number: str) -> Clause | None:
    """Первый пункт с печатным номером number («5.9.1», «5.9.1.а»; точка в конце допустима)."""
    key = number.strip().rstrip(".").translate(_LATIN_TO_CYR).casefold()
    for clause in doc.clauses:
        if clause.number is not None and clause.number.casefold() == key:
            return clause
    return None
