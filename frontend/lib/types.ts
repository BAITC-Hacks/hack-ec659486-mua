/**
 * Типы API — зеркало backend/app/schemas.py (spec §3 + дополнения S01), имена полей 1:1.
 * Файл закрыт после волны 1: не хватает поля — модуль объявляет минимально у себя и пишет в отчёт.
 * Отсутствующее значение — null, не пустая строка.
 */

export type LlmMode = "live" | "mock";

/** GET /health */
export interface Health {
  status: "ok";
  llm_mode: LlmMode;
  model: string;
  version: string;
}

/** GET /api/version */
export interface VersionResponse {
  name: string;
  version: string;
  llm_mode: LlmMode;
}

/** POST /api/example (каркас) */
export interface ExampleRequest {
  text: string;
}

export interface ExampleResponse {
  answer: string;
  llm_mode: LlmMode;
}

/** Единый формат ошибок backend: {"error": "<код>", "detail": ...} */
export interface ApiErrorBody {
  error: string;
  detail?: unknown;
}

// --- Литералы контракта -------------------------------------------------------------------

export type Version = "before" | "after";
export type DocumentKind = "polozhenie" | "di" | "order" | "other";
/** Модальность пункта/функции: обязанность, право, запрет, нейтральное описание. */
export type Modality = "duty" | "right" | "prohibition" | "neutral";
export type FunctionCategory = "task" | "function" | "right" | "duty" | "responsibility";
export type UnitChangeStatus = "kept" | "transformed" | "created" | "abolished";
export type FunctionMatchStatus = "kept" | "changed" | "lost" | "new" | "moved";
/** Форма сопоставления: 1:1, разделение, слияние, частичное. */
export type FunctionMatchKind = "one_to_one" | "split" | "merge" | "partial";
/** Как подтверждено сопоставление: точное совпадение текста, лексическое (сигнатура), LLM. */
export type Verification = "exact" | "lexical" | "llm";
export type Severity = "low" | "medium" | "high";
export type RunState =
  | "queued"
  | "parsing"
  | "units"
  | "functions"
  | "candidates"
  | "verification"
  | "conflicts"
  | "conclusion"
  | "done"
  | "partial"
  | "error";

// --- Документы и пункты (P1) --------------------------------------------------------------

/** Пункт документа — единица прослеживаемости. */
export interface Clause {
  /** Стабильный адрес блока в документе, например "d8:p231:0". */
  id: string;
  /** Печатный номер: "3.2.1", у буквенных подпунктов "5.9.1.а"; null без номера. */
  number: string | null;
  /** Заголовок раздела; null вне разделов. */
  section: string | null;
  /** Путь заголовков от корня документа до пункта. */
  section_path: string[];
  text: string;
  /** Порядковый индекс блока в документе. */
  index: number;
  /** Вводная фраза родительского пункта для подпунктов. */
  lead_in: string | null;
  modality: Modality;
}

export interface Document {
  id: string;
  /** Имя файла как загружено. */
  name: string;
  version: Version;
  kind: DocumentKind;
  clauses: Clause[];
}

/** Ссылка на пункт-источник. Каждый вывод отчёта подтверждён хотя бы одним Source. */
export interface Source {
  doc_id: string;
  doc_name: string;
  version: Version;
  /** Clause.id — стабильный адрес блока. */
  clause_id: string;
  /** Печатный номер пункта; null у ненумерованных блоков. */
  clause_number: string | null;
  /** Дословная цитата из пункта. */
  quote: string;
}

// --- Подразделения (P2) -------------------------------------------------------------------

export interface Unit {
  id: string;
  name: string;
  version: Version;
  /** Unit.id вышестоящего подразделения той же версии. */
  parent: string | null;
  /** Непустой список. */
  sources: Source[];
}

export interface UnitChange {
  id: string;
  unit_before: Unit | null;
  unit_after: Unit | null;
  status: UnitChangeStatus;
  note: string;
  sources: Source[];
}

// --- Функции (P3) и запреты ---------------------------------------------------------------

/** Атомарная функция/задача/право/обязанность с привязкой к пункту. */
export interface Function {
  id: string;
  /** Unit.id; null, если функция не привязана к подразделению. */
  unit_id: string | null;
  text: string;
  category: FunctionCategory;
  modality: Modality;
  /** Исполнитель как в тексте: должность или подразделение. */
  executor: string | null;
  /** Нормализованное действие (глагол). */
  action: string | null;
  /** Нормализованный объект действия. */
  object: string | null;
  /** lib_normalize.signature; null если не построена. */
  signature: string | null;
  /** Номера пунктов контекста (родительский пункт, соседние подпункты). */
  context_clause_numbers: string[];
  sources: Source[];
}

/** Запрет («не вправе», «запрещается») — не функция, показывается отдельно. */
export interface Constraint {
  id: string;
  unit_id: string | null;
  text: string;
  executor: string | null;
  modality: "prohibition";
  sources: Source[];
}

// --- Сопоставление до↔после (P4) ----------------------------------------------------------

/** Строка таблицы сопоставления. lost: after пуст; new: before пуст. */
export interface FunctionMatch {
  id: string;
  before: Function[];
  after: Function[];
  kind: FunctionMatchKind;
  status: FunctionMatchStatus;
  /** Подтверждено кодом (exact/lexical) или проверено LLM. */
  verified: boolean;
  verification: Verification;
  /** 0..1 */
  confidence: number;
  note: string;
  sources: Source[];
}

// --- Дубли и конфликты интересов (P5) -----------------------------------------------------

/** Одинаковая функция у двух разных подразделений одной версии. */
export interface Duplicate {
  id: string;
  function_a: Function;
  function_b: Function;
  /** 0..1 */
  similarity: number;
  note: string;
  verified: boolean;
  verification_note: string;
}

/** Потенциальный конфликт интересов по правилу app/rules/conflicts.py. */
export interface Conflict {
  id: string;
  /** Идентификатор правила, например "executes_and_controls". */
  rule_id: string;
  title: string;
  /** Паттерн ролей: "выполняет + контролирует" и т.п. */
  role_pattern: string;
  severity: Severity;
  /** Unit.id участвующих подразделений. */
  units: string[];
  functions: Function[];
  explanation: string;
  verified: boolean;
  verification_note: string;
  sources: Source[];
}

// --- Отчёт и запуск (P6, API §4) ----------------------------------------------------------

/** Report.stats: все ключи обязательны (0, если нечего считать). */
export interface ReportStats {
  units_before: number;
  units_after: number;
  functions_before: number;
  functions_after: number;
  matches: number;
  lost: number;
  new: number;
  duplicates: number;
  conflicts: number;
  unverified_candidates: number;
  [key: string]: number;
}

export interface Report {
  run_id: string;
  /** ISO 8601, UTC */
  created_at: string;
  before_documents: Document[];
  after_documents: Document[];
  unit_changes: UnitChange[];
  function_matches: FunctionMatch[];
  duplicates: Duplicate[];
  conflicts: Conflict[];
  constraints: Constraint[];
  conclusion_md: string;
  recommendations: string[];
  stats: ReportStats;
}

/** GET /api/runs/{run_id}. partial — часть шагов не выполнена (см. missing_steps). */
export interface RunStatus {
  run_id: string;
  status: RunState;
  /** 0..100 */
  progress: number;
  /** Текст текущего шага или ошибки для пользователя. */
  detail: string | null;
  /** Шаги, которые не удалось выполнить (status=partial). */
  missing_steps: string[];
}

/** POST /api/runs, POST /api/runs/demo */
export interface RunCreated {
  run_id: string;
}
