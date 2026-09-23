"use client";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { Source, UnitChange } from "@/lib/types";

export type SourceHandler = (source: Source) => void;

export function SourceButtons({ sources, onSource }: { sources: Source[]; onSource: SourceHandler }) {
  const unique = sources.filter((source, index) => sources.findIndex((other) =>
    other.doc_id === source.doc_id && other.clause_id === source.clause_id) === index);
  return (
    <div className="flex flex-wrap gap-2">
      {unique.map((source) => (
        <Button key={`${source.doc_id}-${source.clause_id}`} size="sm" variant="secondary"
          title={`${source.version === "before" ? "До" : "После"}: ${source.doc_name}`}
          aria-label={`п. ${source.clause_number ?? "без номера"}, ${source.version === "before" ? "до" : "после"}, ${source.doc_name}`}
          onClick={() => onSource(source)}>
          п. {source.clause_number ?? "без номера"}
        </Button>
      ))}
    </div>
  );
}

export function UnitsTable({ changes, onSource }: { changes: UnitChange[]; onSource: SourceHandler }) {
  const sourced = changes.filter((change) => change.sources.length > 0);
  if (!sourced.length) return <EmptyState title="Подразделения не найдены" />;
  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full min-w-[760px] text-left text-sm">
        <caption className="sr-only">Изменения подразделений с подтверждающими пунктами</caption>
        <thead className="bg-muted"><tr>
          {["Название до", "Название после", "Статус", "Примечание", "Источники"].map((label) => <th key={label} scope="col" className="p-4">{label}</th>)}
        </tr></thead>
        <tbody>{sourced.map((change) => (
          <tr key={change.id} className="border-t border-border align-top">
            <td className="p-4">{change.unit_before?.name ?? "—"}</td>
            <td className="p-4">{change.unit_after?.name ?? "—"}</td>
            <td className="p-4"><StatusBadge status={change.status} /></td>
            <td className="min-w-56 p-4">{change.note}</td>
            <td className="min-w-44 p-4"><SourceButtons sources={change.sources} onSource={onSource} /></td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}
