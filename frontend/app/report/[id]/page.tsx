"use client";

import { useEffect, useRef, useState } from "react";
import { ConclusionView } from "@/components/conclusion-view";
import { ConflictsList } from "@/components/conflicts-list";
import { DuplicatesList } from "@/components/duplicates-list";
import { FunctionMatrix } from "@/components/function-matrix";
import { UnitsTable } from "@/components/units-table";
import { Button } from "@/components/ui/button";
import { Tabs } from "@/components/ui/tabs";
import { demoReport } from "@/lib/fixtures/report";
import type { Report, Source } from "@/lib/types";

const statLabels: Record<string, string> = {
  units_before: "Подразделений до", units_after: "Подразделений после",
  functions_before: "Функций до", functions_after: "Функций после",
  matches: "Сопоставлений", kept: "Сохранённых функций", changed: "Изменённых функций",
  lost: "Утраченных функций", new: "Новых функций", moved: "Перенесённых функций",
  duplicates: "Подтверждённых дублей", conflicts: "Подтверждённых конфликтов",
  unverified_candidates: "Требуют проверки",
};

function SourceDrawer({ source, onClose }: { source: Source | null; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    if (source && element && !element.open) element.showModal();
    if (!source && element?.open) element.close();
  }, [source]);

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
        <div><dt className="text-muted-foreground">Пункт</dt><dd>{source.clause_number ?? "Без номера"}</dd></div>
      </dl>
      <blockquote className="whitespace-pre-wrap border-l-4 border-primary pl-4 leading-relaxed">{source.quote}</blockquote>
    </div>}
  </dialog>;
}

export default function ReportPage() {
  const report: Report = demoReport;
  const [openSource, setOpenSource] = useState<Source | null>(null);
  const unitNames: Record<string, string> = {};
  for (const change of report.unit_changes) {
    for (const unit of [change.unit_before, change.unit_after]) {
      if (unit) unitNames[unit.id] = unit.name;
    }
  }
  const conclusionSources: Source[] = [...report.before_documents, ...report.after_documents].flatMap((doc) =>
    doc.clauses.map((clause) => ({ doc_id: doc.id, doc_name: doc.name, version: doc.version,
      clause_id: clause.id, clause_number: clause.number, quote: clause.text })));

  return <div className="space-y-6">
    <header>
      <p className="text-sm font-medium text-primary">Шаг 3 · Результат</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">Отчёт об изменениях</h1>
      <p className="mt-2 text-sm text-muted-foreground">Запуск: {report.run_id}</p>
      <p className="mt-3 max-w-3xl text-muted-foreground">Выводы носят рекомендательный характер и требуют проверки ответственным сотрудником. Кнопка с номером пункта открывает источник.</p>
    </header>
    <div className="grid gap-4 md:grid-cols-2">
      {([{ label: "Документы до", documents: report.before_documents }, { label: "Документы после", documents: report.after_documents }]).map((group) =>
        <section key={group.label} className="rounded-xl border border-border p-4">
          <h2 className="font-semibold">{group.label}</h2>
          <ul className="mt-2 space-y-2 text-sm text-muted-foreground">{group.documents.map((doc) => <li key={doc.id} className="break-words">{doc.name}</li>)}</ul>
        </section>)}
    </div>
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {Object.entries(report.stats).filter(([key]) => key in statLabels).map(([key, value]) =>
        <div key={key} className="rounded-xl bg-muted p-4"><dt className="text-xs text-muted-foreground">{statLabels[key]}</dt><dd className="mt-1 text-2xl font-semibold tabular-nums">{value}</dd></div>)}
    </dl>
    <Tabs items={[
      { id: "units", label: "Подразделения", content: <UnitsTable changes={report.unit_changes} onSource={setOpenSource} /> },
      { id: "functions", label: "Функции", content: <FunctionMatrix matches={report.function_matches} constraints={report.constraints} unitNames={unitNames} onSource={setOpenSource} /> },
      { id: "duplicates", label: "Дубли и конфликты", content: <div className="space-y-8"><DuplicatesList duplicates={report.duplicates} unitNames={unitNames} onSource={setOpenSource} /><ConflictsList conflicts={report.conflicts} unitNames={unitNames} onSource={setOpenSource} /></div> },
      { id: "conclusion", label: "Заключение", content: <ConclusionView conclusion_md={report.conclusion_md} run_id={report.run_id} sources={conclusionSources} onSource={setOpenSource} /> },
    ]} />
    <SourceDrawer source={openSource} onClose={() => setOpenSource(null)} />
  </div>;
}
