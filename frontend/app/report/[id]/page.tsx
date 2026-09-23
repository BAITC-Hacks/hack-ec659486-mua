"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ConclusionView } from "@/components/conclusion-view";
import { ConflictsList } from "@/components/conflicts-list";
import { DuplicatesList } from "@/components/duplicates-list";
import { FunctionMatrix } from "@/components/function-matrix";
import { SourceDrawer } from "@/components/source-drawer";
import { UnitsTable } from "@/components/units-table";
import { Tabs } from "@/components/ui/tabs";
import { ApiError } from "@/lib/api";
import { getReport, useFixtures } from "@/lib/api-runs";
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

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const fixturesEnabled = useFixtures();
  const [report, setReport] = useState<Report | null>(null);
  const [fixture, setFixture] = useState(false);
  const [error, setError] = useState<{ message: string; notReady: boolean } | null>(null);
  const [openSource, setOpenSource] = useState<Source | null>(null);

  useEffect(() => {
    let active = true;
    if (fixturesEnabled) {
      setReport(demoReport);
      setFixture(true);
      return () => { active = false; };
    }
    void getReport(id).then((result) => {
      if (!active) return;
      setReport(result);
      setFixture(false);
    }).catch((cause: unknown) => {
      if (!active) return;
      if (id === "demo" && cause instanceof ApiError && cause.status === 0) {
        setReport(demoReport);
        setFixture(true);
      } else {
        setError({
          message: cause instanceof Error ? cause.message : "Не удалось загрузить отчёт.",
          notReady: cause instanceof ApiError && cause.status === 404,
        });
      }
    });
    return () => { active = false; };
  }, [id, fixturesEnabled]);

  if (error) return <div role="alert" className="space-y-3 rounded-xl border border-border p-6">
    <h1 className="text-xl font-semibold">{error.notReady ? "Отчёт ещё не готов" : "Не удалось загрузить отчёт"}</h1>
    <p>{error.message}</p>
    {error.notReady && <Link href={`/runs/${encodeURIComponent(id)}`} className="text-primary underline">Вернуться к ходу анализа</Link>}
  </div>;
  if (!report) return <p className="text-muted-foreground" role="status">Загружаем отчёт…</p>;

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
      {fixture && <p className="mt-2 text-sm text-amber-700">Показана демонстрационная фикстура.</p>}
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
    <SourceDrawer key={openSource ? `${openSource.doc_id}:${openSource.clause_id}` : "closed"} runId={id} source={openSource} onClose={() => setOpenSource(null)} />
  </div>;
}
