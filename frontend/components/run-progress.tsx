import { Check, LoaderCircle } from "lucide-react";
import type { RunState, RunStatus } from "@/lib/types";

const steps: { state: RunState; label: string }[] = [
  { state: "parsing", label: "Разбор" },
  { state: "units", label: "Подразделения" },
  { state: "functions", label: "Функции" },
  { state: "candidates", label: "Кандидаты" },
  { state: "verification", label: "Проверка" },
  { state: "conflicts", label: "Конфликты" },
  { state: "conclusion", label: "Заключение" },
];

export function RunProgress({ status }: { status: RunStatus }) {
  const current = steps.findIndex((step) => step.state === status.status);
  const finished = status.status === "done" || status.status === "partial";
  const progress = Math.max(0, Math.min(100, status.progress));

  return <div className="space-y-6">
    <div aria-label={`Прогресс: ${progress} %`}>
      <div className="flex justify-between text-sm"><span>Прогресс</span><span className="tabular-nums">{progress} %</span></div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}>
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${progress}%` }} />
      </div>
    </div>
    {status.status === "queued" && <p className="text-sm text-muted-foreground">Анализ в очереди.</p>}
    <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {steps.map((step, index) => {
        const complete = finished || (current >= 0 && index < current);
        const active = current === index;
        return <li key={step.state} aria-current={active ? "step" : undefined}
          className={`flex items-center gap-3 rounded-xl border p-4 ${active ? "border-primary bg-primary/10 font-semibold" : complete ? "border-primary/40 text-foreground" : "border-border text-muted-foreground"}`}>
          <span className={`flex size-7 shrink-0 items-center justify-center rounded-full ${complete ? "bg-primary text-primary-foreground" : active ? "text-primary" : "bg-muted"}`}>
            {complete ? <Check className="size-4" aria-hidden="true" /> : active ? <LoaderCircle className="size-5 animate-spin" aria-hidden="true" /> : index + 1}
          </span>
          {step.label}
        </li>;
      })}
    </ol>
    {status.status === "error" && <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-4 text-red-800">{status.detail}</div>}
  </div>;
}
