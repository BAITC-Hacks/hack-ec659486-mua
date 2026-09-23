"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { Health } from "@/lib/types";

type HealthState =
  | { status: "loading" }
  | { status: "ok"; health: Health }
  | { status: "error"; message: string };

export interface HealthBadgeProps {
  /** Период опроса /health, мс. */
  intervalMs?: number;
}

/** Индикатор в шапке: состояние API и режим LLM. Опрашивает /health каждые 10 секунд. */
export function HealthBadge({ intervalMs = 10_000 }: HealthBadgeProps) {
  const [state, setState] = useState<HealthState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const health = await api<Health>("/health", { cache: "no-store" });
        if (!cancelled) {
          setState({ status: "ok", health });
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : String(err);
          setState({ status: "error", message });
        }
      }
    }

    void check();
    const id = setInterval(check, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [intervalMs]);

  if (state.status === "loading") {
    return (
      <Badge variant="muted" title={t("loading")}>
        <span className="size-2 rounded-full bg-muted-foreground/60" />
        API
      </Badge>
    );
  }

  if (state.status === "error") {
    return (
      <Badge variant="danger" title={state.message}>
        <span className="size-2 rounded-full bg-danger" />
        {t("apiUnavailable")}
      </Badge>
    );
  }

  const { health } = state;
  const live = health.llm_mode === "live";
  return (
    <span className="flex items-center gap-2">
      <Badge variant="success" title={`${t("apiOk")} · v${health.version}`}>
        <span className="size-2 rounded-full bg-success" />
        API
      </Badge>
      <Badge variant={live ? "default" : "warning"} title={`model: ${health.model}`}>
        LLM: {health.llm_mode}
      </Badge>
    </span>
  );
}
