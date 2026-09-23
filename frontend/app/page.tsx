import { ArrowRight, Bot, Server } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { api, ApiError } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { Health } from "@/lib/types";

// Страница рендерится на каждый запрос (ходит в /health), а не при сборке.
export const dynamic = "force-dynamic";

const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || "ОргДифф";
// Публичный адрес API (тот, что видит браузер); серверный fetch может идти по API_URL_INTERNAL.
const PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Screen {
  href: string;
  title: string;
  description: string;
}

/** Список экранов проекта. Добавляйте сюда страницы по мере появления. */
const SCREENS: Screen[] = [
  {
    href: "/example",
    title: "Пример вызова LLM",
    description: "POST /api/example — шаблон экрана «форма → API → результат».",
  },
];

type HealthState = { health: Health; error: null } | { health: null; error: string };

/** Не бросает исключений: если backend недоступен, страница всё равно рендерится. */
async function loadHealth(): Promise<HealthState> {
  try {
    const health = await api<Health>("/health", { cache: "no-store" });
    return { health, error: null };
  } catch (err) {
    if (err instanceof ApiError) {
      return { health: null, error: err.message };
    }
    return { health: null, error: err instanceof Error ? err.message : t("error") };
  }
}

export default async function HomePage() {
  const { health, error } = await loadHealth();
  const live = health?.llm_mode === "live";

  return (
    <div className="space-y-10">
      <section>
        <h1 className="text-3xl font-bold tracking-tight">{APP_NAME}</h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Каркас без доменной логики: FastAPI + Next.js, OpenAI Responses API с mock-режимом,
          единый формат ошибок, Docker Compose и CI.
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="size-4" aria-hidden="true" />
              API
            </CardTitle>
            <CardDescription>{PUBLIC_API_URL}</CardDescription>
          </CardHeader>
          <CardContent>
            {health ? (
              <dl className="grid grid-cols-2 gap-y-1 text-sm">
                <dt className="text-muted-foreground">Статус</dt>
                <dd>
                  <Badge variant="success">{health.status}</Badge>
                </dd>
                <dt className="text-muted-foreground">Версия</dt>
                <dd>{health.version}</dd>
              </dl>
            ) : (
              <div className="text-sm">
                <Badge variant="danger">{t("apiUnavailable")}</Badge>
                <p className="mt-2 text-muted-foreground">{error}</p>
                <p className="mt-2 text-muted-foreground">
                  Запустите backend: <code>make backend</code> или <code>docker compose up</code>.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="size-4" aria-hidden="true" />
              LLM
            </CardTitle>
            <CardDescription>Режим и модель из настроек backend</CardDescription>
          </CardHeader>
          <CardContent>
            {health ? (
              <dl className="grid grid-cols-2 gap-y-1 text-sm">
                <dt className="text-muted-foreground">Режим</dt>
                <dd>
                  <Badge variant={live ? "default" : "warning"}>{health.llm_mode}</Badge>
                </dd>
                <dt className="text-muted-foreground">Модель</dt>
                <dd>{health.model}</dd>
              </dl>
            ) : (
              <Badge variant="muted">неизвестно</Badge>
            )}
            {health && !live ? (
              <p className="mt-3 text-sm text-muted-foreground">
                Mock-режим: ответы берутся из <code>backend/app/mocks/</code>. Для live-режима
                задайте <code>OPENAI_API_KEY</code> и <code>LLM_MODE=live</code> в <code>.env</code>.
              </p>
            ) : null}
          </CardContent>
        </Card>
      </section>

      <section>
        <h2 className="mb-3 text-xl font-semibold">Экраны</h2>
        {SCREENS.length === 0 ? (
          <EmptyState
            title={t("empty")}
            description="Добавьте страницы в app/ и перечислите их в SCREENS на главной."
          />
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {SCREENS.map((screen) => (
              <li key={screen.href}>
                <Link
                  href={screen.href}
                  className="flex items-center justify-between gap-3 rounded-xl border border-border bg-card p-4 transition-colors hover:bg-muted"
                >
                  <span>
                    <span className="block font-medium">{screen.title}</span>
                    <span className="block text-sm text-muted-foreground">{screen.description}</span>
                  </span>
                  <ArrowRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
