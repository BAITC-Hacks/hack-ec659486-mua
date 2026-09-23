/**
 * Типы API — зеркало backend/app/schemas.py. Contract-first: меняем здесь и там одновременно.
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

/** POST /api/example */
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
