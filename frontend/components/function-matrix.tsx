"use client";

import { useState } from "react";
import { StatusBadge } from "@/components/status-badge";
import { EmptyState } from "@/components/ui/empty-state";
import { SourceButtons, type SourceHandler } from "@/components/units-table";
import type { Constraint, Function as ReportFunction, FunctionMatch, FunctionMatchStatus } from "@/lib/types";

const kinds = { one_to_one: "Один-к-одному", split: "Разделена", merge: "Объединена", partial: "Частично" };
const filters: { value: FunctionMatchStatus | "all"; label: string }[] = [
  { value: "all", label: "Все" }, { value: "kept", label: "Сохранена" },
  { value: "changed", label: "Изменена" }, { value: "lost", label: "Утрачена" },
  { value: "new", label: "Новая" }, { value: "moved", label: "Перенесена" },
];

export function FunctionDetails({ functions, unitNames = {}, onSource }: {
  functions: ReportFunction[]; unitNames?: Record<string, string>; onSource: SourceHandler;
}) {
  if (!functions.length) return <span className="text-muted-foreground">—</span>;
  return <div className="space-y-4">{functions.filter((item) => item.sources.length > 0).map((item) => (
    <div key={item.id} className="space-y-2">
      <p className="whitespace-pre-line">{item.text}</p>
      <p className="text-xs text-muted-foreground">
        Подразделение: {item.unit_id ? unitNames[item.unit_id] ?? item.unit_id : "не указано"}
        {item.executor ? ` · Исполнитель: ${item.executor}` : ""}
      </p>
      <SourceButtons sources={item.sources} onSource={onSource} />
    </div>
  ))}</div>;
}

export function FunctionMatrix({ matches, constraints, onSource, unitNames = {} }: {
  matches: FunctionMatch[]; constraints: Constraint[]; onSource: SourceHandler; unitNames?: Record<string, string>;
}) {
  const [filter, setFilter] = useState<FunctionMatchStatus | "all">("all");
  const sourced = matches.filter((match) => match.sources.length > 0 &&
    [...match.before, ...match.after].every((item) => item.sources.length > 0));
  const verified = sourced.filter((match) => match.verified);
  const candidates = sourced.filter((match) => !match.verified);
  const visible = verified.filter((match) => filter === "all" || match.status === filter);
  const restrictions = constraints.filter((item) => item.sources.length > 0);

  function matchTable(rows: FunctionMatch[]) {
    return <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full min-w-[900px] text-left text-sm">
        <caption className="sr-only">Сопоставление функций до и после реорганизации</caption>
        <thead className="bg-muted"><tr>{["Функции до", "Функции после", "Вид связи", "Статус и проверка", "Уверенность", "Обоснование и источники"].map((label) =>
          <th key={label} scope="col" className="p-4">{label}</th>)}</tr></thead>
        <tbody>{rows.map((match) => <tr key={match.id} className="border-t border-border align-top">
          <td className="min-w-64 p-4"><FunctionDetails functions={match.before} unitNames={unitNames} onSource={onSource} /></td>
          <td className="min-w-64 p-4"><FunctionDetails functions={match.after} unitNames={unitNames} onSource={onSource} /></td>
          <td className="p-4">{kinds[match.kind]}</td>
          <td className="p-4"><StatusBadge status={match.status} verified={match.verified} verification={match.verification} /></td>
          <td className="p-4">{Math.round(match.confidence * 100)}%</td>
          <td className="min-w-64 space-y-3 p-4"><p>{match.note}</p><SourceButtons sources={match.sources} onSource={onSource} /></td>
        </tr>)}</tbody>
      </table>
    </div>;
  }

  return <div className="space-y-8">
    <section className="space-y-4" aria-label="Проверенные сопоставления">
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="function-status" className="text-sm font-medium">Статус функции</label>
        <select id="function-status" value={filter} onChange={(event) => setFilter(event.target.value as typeof filter)}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm">
          {filters.map((item) => <option key={item.value} value={item.value}>
            {item.label} ({verified.filter((match) => item.value === "all" || match.status === item.value).length})
          </option>)}
        </select>
        <p role="status" className="text-sm text-muted-foreground">Показано строк: {visible.length} из {verified.length}</p>
      </div>
      {visible.length ? matchTable(visible) : <EmptyState title="Сопоставления не найдены" description="Для выбранного статуса нет проверенных сопоставлений с источниками." />}
    </section>
    <section className="space-y-4">
      <h2 className="text-xl font-semibold">Кандидаты в потери — требует проверки</h2>
      <p className="text-sm text-muted-foreground">Эти сопоставления ещё не подтверждены и не учитываются как доказанные потери.</p>
      {candidates.length ? matchTable(candidates) : <EmptyState title="Непроверенных кандидатов нет" />}
    </section>
    <section className="space-y-4">
      <h2 className="text-xl font-semibold">Ограничения</h2>
      {restrictions.length ? <ul className="space-y-3">{restrictions.map((item) => <li key={item.id} className="space-y-3 rounded-xl border border-border p-4">
        <p>{item.text}</p><p className="text-sm text-muted-foreground">Исполнитель: {item.executor ?? "не указан"}</p>
        <SourceButtons sources={item.sources} onSource={onSource} />
      </li>)}</ul> : <EmptyState title="Ограничения не найдены" />}
    </section>
  </div>;
}
