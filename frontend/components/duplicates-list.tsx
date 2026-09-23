"use client";

import { FunctionDetails } from "@/components/function-matrix";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import type { SourceHandler } from "@/components/units-table";
import type { Duplicate } from "@/lib/types";

export function DuplicatesList({ duplicates, unitNames = {}, onSource }: {
  duplicates: Duplicate[]; unitNames?: Record<string, string>; onSource: SourceHandler;
}) {
  const sourced = duplicates.filter((item) => item.function_a.sources.length > 0 && item.function_b.sources.length > 0);
  return <section className="space-y-4">
    <h2 className="text-xl font-semibold">Дубли функций</h2>
    {[true, false].map((verified) => {
      const items = sourced.filter((item) => item.verified === verified);
      return <div key={String(verified)} className="space-y-3">
        <h3 className="font-medium">{verified ? "Подтверждённые дубли" : "Кандидаты в дубли — требует проверки"}</h3>
        {items.length ? items.map((item) => <article key={item.id} className="space-y-4 rounded-xl border border-border p-4">
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm">Сходство: {Math.round(item.similarity * 100)}%</p>
            {!item.verified && <Badge variant="warning">Требует проверки</Badge>}
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            <FunctionDetails functions={[item.function_a]} unitNames={unitNames} onSource={onSource} />
            <FunctionDetails functions={[item.function_b]} unitNames={unitNames} onSource={onSource} />
          </div>
          {item.note && <p className="text-sm">{item.note}</p>}
          <p className="text-sm text-muted-foreground">Проверка: {item.verification_note}</p>
        </article>) : <EmptyState title={verified ? "Подтверждённых дублей нет" : "Кандидатов в дубли нет"} />}
      </div>;
    })}
  </section>;
}
