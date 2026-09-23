"""Pydantic-контракты API «ОргДифф» (spec §3 + дополнения S01). Зеркало: frontend/lib/types.ts.

Правила контракта (обязательны для всех сессий):
- Все поля обязательные, лишние поля запрещены (extra="forbid"). Отсутствующее значение — None,
  не пустая строка.
- Enum-статусы — строковые Literal, одни и те же имена здесь и в types.ts.
- Каждая находка (Unit, UnitChange, Function, FunctionMatch, Constraint, Conflict) несёт
  непустой список Source: находка без источника не проходит валидацию и не показывается.
- Файл закрыт после волны 1. Не хватает поля — модуль добавляет минимально у себя и пишет
  об этом в отчёт, интегратор решает.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- Общие модели каркаса ------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Единый формат ошибок API (см. обработчики в app.main)."""

    error: str = Field(description="Машиночитаемый код ошибки", examples=["validation_error"])
    detail: object | None = Field(default=None, description="Подробности (строка или список)")


class VersionResponse(BaseModel):
    name: str
    version: str
    llm_mode: str = Field(description="Фактический режим LLM: live или mock")


# --- Пример эндпоинта /api/example (каркас, используется тестами test_health.py) ------------


class ExampleRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000, description="Произвольный текст пользователя")


class ExampleLLMOutput(BaseModel):
    """Схема структурированного ответа LLM.

    Используется и для JSON Schema (strict_schema), и для валидации ответа/фикстуры.
    Для strict-режима Structured Outputs все поля должны быть обязательными.

    extra="forbid" обязателен: strict_schema ставит additionalProperties=false в схему
    для провайдера, но обычный BaseModel лишнее поле молча отбрасывал — локальная
    проверка была слабее заявленной. Все схемы ответов LLM объявлять так же.
    """

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(description="Краткий ответ на текст пользователя")


class ExampleResponse(BaseModel):
    answer: str
    llm_mode: str


# --- Литералы контракта (spec §3, §4 + дополнения S01) -------------------------------------

Version = Literal["before", "after"]
DocumentKind = Literal["polozhenie", "di", "order", "other"]
# Модальность пункта/функции: обязанность, право, запрет, нейтральное описание.
Modality = Literal["duty", "right", "prohibition", "neutral"]
FunctionCategory = Literal["task", "function", "right", "duty", "responsibility"]
UnitChangeStatus = Literal["kept", "transformed", "created", "abolished"]
FunctionMatchStatus = Literal["kept", "changed", "lost", "new", "moved"]
# Форма сопоставления: 1:1, одна функция «до» разделилась, несколько слились, частичное.
FunctionMatchKind = Literal["one_to_one", "split", "merge", "partial"]
# Как подтверждено сопоставление: точное совпадение текста, лексическое (сигнатура), LLM.
Verification = Literal["exact", "lexical", "llm"]
Severity = Literal["low", "medium", "high"]
RunState = Literal[
    "queued",
    "parsing",
    "units",
    "functions",
    "candidates",
    "verification",
    "conflicts",
    "conclusion",
    "done",
    "partial",
    "error",
]

# Ключи Report.stats — все обязательны (значение 0, если нечего считать).
STATS_KEYS: tuple[str, ...] = (
    "units_before",
    "units_after",
    "functions_before",
    "functions_after",
    "matches",
    "lost",
    "new",
    "duplicates",
    "conflicts",
    "unverified_candidates",
)


class StrictModel(BaseModel):
    """База контракта: лишние поля запрещены, все поля обязательны."""

    model_config = ConfigDict(extra="forbid")


# --- Документы и пункты (P1) ---------------------------------------------------------------


class Clause(StrictModel):
    """Пункт документа — единица прослеживаемости."""

    id: str = Field(description="Стабильный адрес блока в документе, например 'd8:p231:0'")
    number: str | None = Field(
        description="Печатный номер: '3.2.1', у буквенных подпунктов '5.9.1.а'; None без номера"
    )
    section: str | None = Field(
        description="Заголовок раздела, в котором стоит пункт; None вне разделов"
    )
    section_path: list[str] = Field(description="Путь заголовков от корня документа до пункта")
    text: str = Field(description="Текст пункта как в документе")
    index: int = Field(ge=0, description="Порядковый индекс блока в документе")
    lead_in: str | None = Field(
        description="Вводная фраза родительского пункта для подпунктов ('... в части:')"
    )
    modality: Modality


class Document(StrictModel):
    id: str
    name: str = Field(description="Имя файла как загружено")
    version: Version
    kind: DocumentKind
    clauses: list[Clause]


class Source(StrictModel):
    """Ссылка на пункт-источник. Каждый вывод отчёта подтверждён хотя бы одним Source."""

    doc_id: str
    doc_name: str
    version: Version
    clause_id: str = Field(description="Clause.id — стабильный адрес блока")
    clause_number: str | None = Field(
        description="Печатный номер пункта; None у ненумерованных блоков"
    )
    quote: str = Field(description="Дословная цитата из пункта")


# --- Подразделения (P2) --------------------------------------------------------------------


class Unit(StrictModel):
    id: str
    name: str
    version: Version
    parent: str | None = Field(description="Unit.id вышестоящего подразделения той же версии")
    sources: list[Source] = Field(min_length=1)


class UnitChange(StrictModel):
    id: str = Field(description="Добавлено S01: адрес находки для ссылок из заключения и ключей UI")
    unit_before: Unit | None
    unit_after: Unit | None
    status: UnitChangeStatus
    note: str
    sources: list[Source] = Field(min_length=1)


# --- Функции (P3) и запреты ----------------------------------------------------------------


class Function(StrictModel):
    """Атомарная функция/задача/право/обязанность с привязкой к пункту."""

    id: str
    unit_id: str | None = Field(
        description="Unit.id; None, если функция не привязана к подразделению"
    )
    text: str
    category: FunctionCategory
    modality: Modality
    executor: str | None = Field(
        description="Исполнитель как в тексте: должность или подразделение"
    )
    action: str | None = Field(
        description="Нормализованное действие (глагол), None если не выделено"
    )
    object: str | None = Field(description="Нормализованный объект действия, None если не выделен")
    signature: str | None = Field(description="lib_normalize.signature; None если не построена")
    context_clause_numbers: list[str] = Field(
        description="Номера пунктов контекста (родительский пункт, соседние подпункты)"
    )
    sources: list[Source] = Field(min_length=1)


class Constraint(StrictModel):
    """Запрет («не вправе», «запрещается») — не функция, показывается отдельно."""

    id: str = Field(description="Добавлено S01: адрес находки")
    unit_id: str | None = Field(description="Добавлено S01: Unit.id, к которому относится запрет")
    text: str
    executor: str | None
    modality: Literal["prohibition"]
    sources: list[Source] = Field(min_length=1)


# --- Сопоставление до↔после (P4) -----------------------------------------------------------


class FunctionMatch(StrictModel):
    """Строка таблицы сопоставления. lost: after пуст; new: before пуст."""

    id: str = Field(description="Добавлено S01: адрес находки")
    before: list[Function]
    after: list[Function]
    kind: FunctionMatchKind
    status: FunctionMatchStatus
    verified: bool = Field(description="Подтверждено кодом (exact/lexical) или проверено LLM")
    verification: Verification
    confidence: float = Field(ge=0.0, le=1.0)
    note: str
    sources: list[Source] = Field(min_length=1)


# --- Дубли и конфликты интересов (P5) ------------------------------------------------------


class Duplicate(StrictModel):
    """Одинаковая функция у двух разных подразделений одной версии."""

    id: str = Field(description="Добавлено S01: адрес находки")
    function_a: Function
    function_b: Function
    similarity: float = Field(ge=0.0, le=1.0)
    note: str
    verified: bool
    verification_note: str


class Conflict(StrictModel):
    """Потенциальный конфликт интересов по правилу app/rules/conflicts.py."""

    id: str = Field(description="Добавлено S01: адрес находки")
    rule_id: str = Field(description="Идентификатор правила, например 'executes_and_controls'")
    title: str
    role_pattern: str = Field(description="Паттерн ролей: 'выполняет + контролирует' и т.п.")
    severity: Severity
    units: list[str] = Field(description="Unit.id участвующих подразделений")
    functions: list[Function]
    explanation: str
    verified: bool
    verification_note: str
    sources: list[Source] = Field(min_length=1)


# --- Отчёт и запуск (P6, API §4) -----------------------------------------------------------


class Report(StrictModel):
    run_id: str
    created_at: str = Field(description="ISO 8601, UTC")
    before_documents: list[Document]
    after_documents: list[Document]
    unit_changes: list[UnitChange]
    function_matches: list[FunctionMatch]
    duplicates: list[Duplicate]
    conflicts: list[Conflict]
    constraints: list[Constraint]
    conclusion_md: str
    recommendations: list[str]
    stats: dict[str, int] = Field(description=f"Обязательные ключи: {', '.join(STATS_KEYS)}")

    @field_validator("stats")
    @classmethod
    def _stats_have_required_keys(cls, value: dict[str, int]) -> dict[str, int]:
        missing = [key for key in STATS_KEYS if key not in value]
        if missing:
            raise ValueError(f"в stats нет обязательных ключей: {', '.join(missing)}")
        return value


def empty_stats() -> dict[str, int]:
    """Все обязательные ключи stats со значением 0."""
    return dict.fromkeys(STATS_KEYS, 0)


class RunStatus(StrictModel):
    """GET /api/runs/{run_id}. partial — часть шагов не выполнена (см. missing_steps)."""

    run_id: str = Field(description="Добавлено S01: идентификатор запуска в ответе статуса")
    status: RunState
    progress: int = Field(ge=0, le=100)
    detail: str | None = Field(description="Текст текущего шага или ошибки для пользователя")
    missing_steps: list[str] = Field(
        description="Шаги, которые не удалось выполнить (status=partial)"
    )


class RunCreated(StrictModel):
    """POST /api/runs, POST /api/runs/demo."""

    run_id: str
