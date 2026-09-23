/**
 * Типизированный fetch-хелпер к backend.
 *
 *   const health = await api<Health>("/health", { cache: "no-store" });
 *   const res = await postJson<ExampleResponse>("/api/example", { text });
 *
 * Бросает ApiError(status, message, body) на HTTP-ошибки и на сетевые сбои (status = 0).
 * Базовый URL: в браузере NEXT_PUBLIC_API_URL; на сервере (SSR, Docker) — API_URL_INTERNAL,
 * если задан (в docker-compose это http://backend:8000), иначе NEXT_PUBLIC_API_URL.
 */

import type { ApiErrorBody } from "@/lib/types";

const DEFAULT_API_URL = "http://localhost:8000";

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function stripTrailingSlash(url: string): string {
  return url.replace(/\/+$/, "");
}

/** Базовый URL API для текущей среды выполнения (сервер или браузер). */
export function apiBaseUrl(): string {
  const publicUrl = process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL;
  if (typeof window === "undefined") {
    return stripTrailingSlash(process.env.API_URL_INTERNAL || publicUrl);
  }
  return stripTrailingSlash(publicUrl);
}

/** Достаёт человекочитаемое сообщение из тела ошибки backend. */
function extractMessage(status: number, body: unknown): string {
  if (body && typeof body === "object") {
    const { error, detail } = body as Partial<ApiErrorBody>;
    if (typeof detail === "string" && detail) {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      // Формат ошибок валидации Pydantic: [{loc: [...], msg: "...", type: "..."}]
      const first = detail[0] as { msg?: unknown; loc?: unknown };
      if (typeof first.msg === "string") {
        const loc = Array.isArray(first.loc) ? first.loc.slice(1).join(".") : "";
        return loc ? `${loc}: ${first.msg}` : first.msg;
      }
    }
    if (typeof error === "string" && error) {
      return error;
    }
  }
  return `HTTP ${status}`;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const url = `${apiBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`;

  const headers = new Headers(init.headers);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  // FormData сам проставляет multipart-границу: свой Content-Type её затрёт и импорт файлов сломается.
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
  if (init.body !== undefined && init.body !== null && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(url, { ...init, headers });
  } catch (cause) {
    throw new ApiError(0, `Не удалось подключиться к API (${url})`, cause);
  }

  const raw = await response.text();
  let body: unknown = null;
  if (raw) {
    try {
      body = JSON.parse(raw);
    } catch {
      body = raw;
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, extractMessage(response.status, body), body);
  }
  return body as T;
}

export function postJson<T>(path: string, data: unknown, init: RequestInit = {}): Promise<T> {
  return api<T>(path, { ...init, method: "POST", body: JSON.stringify(data) });
}
