"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { LoaderCircle } from "lucide-react";
import { RunProgress } from "@/components/run-progress";
import { ApiError } from "@/lib/api";
import { getRun } from "@/lib/api-runs";
import type { RunStatus } from "@/lib/types";

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [requestError, setRequestError] = useState<{ message: string; offline: boolean } | null>(null);

  useEffect(() => {
    let active = true;
    let pending = false;
    const timer = setInterval(() => { void poll(); }, 2000);

    async function poll() {
      if (pending) return;
      pending = true;
      try {
        const next = await getRun(id);
        if (!active) return;
        setStatus(next);
        setRequestError(null);
        if (next.status === "done") {
          clearInterval(timer);
          router.replace(`/report/${encodeURIComponent(id)}`);
        } else if (next.status === "error" || next.status === "partial") {
          clearInterval(timer);
        }
      } catch (error) {
        if (!active) return;
        setRequestError({
          message: error instanceof Error ? error.message : "Не удалось получить статус анализа.",
          offline: error instanceof ApiError && error.status === 0,
        });
        if (!(error instanceof ApiError && error.status === 0)) clearInterval(timer);
      } finally {
        pending = false;
      }
    }

    void poll();
    return () => { active = false; clearInterval(timer); };
  }, [id, router]);

  return <div className="space-y-6">
    <header>
      <p className="text-sm font-medium text-primary">Шаг 2 · Анализ</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">Ход анализа</h1>
    </header>
    {!status && !requestError && <p className="flex items-center gap-2 text-muted-foreground"><LoaderCircle className="size-5 animate-spin" aria-hidden="true" />Запрашиваем статус…</p>}
    {requestError && <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-4 text-red-800">
      <p>{requestError.message}</p>
      {requestError.offline && <p className="mt-2">Проверьте, запущен ли backend на :8000. Повторяем запрос каждые 2 секунды.</p>}
    </div>}
    {status && <RunProgress status={status} />}
    {status?.status === "error" && <Link href="/" className="inline-block text-primary underline">Загрузить заново</Link>}
    {status?.status === "partial" && <Link href={`/report/${encodeURIComponent(id)}`} className="inline-block text-primary underline">Открыть частичный отчёт</Link>}
  </div>;
}
