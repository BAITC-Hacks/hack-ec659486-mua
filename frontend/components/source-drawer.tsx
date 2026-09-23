"use client";

import { useEffect, useRef, useState } from "react";
import { LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getClause } from "@/lib/api-runs";
import type { Clause, Source } from "@/lib/types";

export function SourceDrawer({ runId, source, onClose }: { runId: string; source: Source | null; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [clause, setClause] = useState<Clause | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const element = dialog.current;
    if (source && element && !element.open) element.showModal();
    if (!source && element?.open) element.close();
  }, [source]);

  useEffect(() => {
    if (!source) return;
    let active = true;
    setClause(null);
    setError(null);
    setLoading(true);
    void getClause(runId, source.doc_id, source.clause_number ?? source.clause_id)
      .then((result) => { if (active) setClause(result); })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "Неизвестная ошибка"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [runId, source]);

  return <dialog ref={dialog} aria-labelledby="source-title"
    onCancel={(event) => { event.preventDefault(); onClose(); }}
    className="fixed inset-y-0 right-0 left-auto m-0 h-dvh max-h-dvh w-full max-w-lg overflow-y-auto border-l border-border bg-card p-6 text-foreground shadow-xl backdrop:bg-black/40">
    {source && <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h2 id="source-title" className="text-xl font-semibold">Источник вывода</h2>
        <Button variant="secondary" onClick={onClose} autoFocus>Закрыть</Button>
      </div>
      <dl className="space-y-4 text-sm">
        <div><dt className="text-muted-foreground">Документ</dt><dd className="mt-1 break-words">{source.doc_name}</dd></div>
        <div><dt className="text-muted-foreground">Версия</dt><dd>{source.version === "before" ? "До реорганизации" : "После реорганизации"}</dd></div>
        {clause?.section && <div><dt className="text-muted-foreground">Раздел</dt><dd>{clause.section}</dd></div>}
        <div><dt className="text-muted-foreground">Пункт</dt><dd>{clause?.number ?? source.clause_number ?? "Без номера"}</dd></div>
      </dl>
      {loading && <p className="flex items-center gap-2 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" aria-hidden="true" />Загружаем полный текст пункта…</p>}
      {error && <p role="alert" className="text-sm text-red-700">Полный текст пункта недоступен: {error}</p>}
      <blockquote className="whitespace-pre-wrap border-l-4 border-primary pl-4 leading-relaxed">{clause?.text || source.quote}</blockquote>
    </div>}
  </dialog>;
}
