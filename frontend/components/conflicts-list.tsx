"use client";

import { FunctionDetails } from "@/components/function-matrix";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { SourceButtons, type SourceHandler } from "@/components/units-table";
import type { Conflict } from "@/lib/types";

const severityLabels = { low: "Низкая", medium: "Средняя", high: "Высокая" };

export function ConflictsList({ conflicts, unitNames = {}, onSource }: {
  conflicts: Conflict[]; unitNames?: Record<string, string>; onSource: SourceHandler;
}) {
  const sourced = conflicts.filter((item) => item.sources.length > 0 && item.functions.every((fn) => fn.sources.length > 0));
  return <section className="space-y-4">
    <h2 className="text-xl font-semibold">Конфликты интересов</h2>
    {[true, false].map((verified) => {
      const items = sourced.filter((item) => item.verified === verified);
      return <div key={String(verified)} className="space-y-3">
        <h3 className="font-medium">{verified ? "Подтверждённые находки" : "Возможные конфликты — требует проверки"}</h3>
        {items.length ? items.map((item) => <article key={item.id} className="space-y-4 rounded-xl border border-border p-4">
          <div className="flex flex-wrap items-center gap-3"><h4 className="font-semibold">{item.title}</h4>
            {!item.verified && <Badge variant="warning">Требует проверки</Badge>}
          </div>
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div><dt className="text-muted-foreground">Правило</dt><dd>{item.rule_id}</dd></div>
            <div><dt className="text-muted-foreground">Шаблон ролей</dt><dd>{item.role_pattern}</dd></div>
            <div><dt className="text-muted-foreground">Серьёзность</dt><dd>{severityLabels[item.severity]}</dd></div>
            <div><dt className="text-muted-foreground">Подразделения</dt><dd>{item.units.map((id) => unitNames[id] ?? id).join("; ") || "Не указаны"}</dd></div>
          </dl>
          <p>{item.explanation}</p>
          <p className="text-sm text-muted-foreground">Проверка: {item.verification_note}</p>
          <FunctionDetails functions={item.functions} unitNames={unitNames} onSource={onSource} />
          <SourceButtons sources={item.sources} onSource={onSource} />
        </article>) : <EmptyState title={verified ? "Подтверждённых конфликтов нет" : "Кандидатов в конфликты нет"} />}
      </div>;
    })}
  </section>;
}
