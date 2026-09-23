import { EmptyState } from "@/components/ui/empty-state";
import { Tabs } from "@/components/ui/tabs";

const sections = [
  { id: "units", label: "Подразделения", description: "Здесь появятся сохранённые, преобразованные и новые подразделения." },
  { id: "functions", label: "Функции", description: "Здесь появится сравнение функций до и после реорганизации." },
  { id: "duplicates", label: "Дубли и конфликты", description: "Здесь появятся возможные пересечения зон ответственности." },
  { id: "conclusion", label: "Заключение", description: "Здесь появится аналитическое заключение со ссылками на источники." },
] as const;

export default function ReportPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium text-primary">Шаг 3 · Результат</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Отчёт об изменениях</h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          Каждый существенный вывод должен открывать подтверждающий пункт документа.
        </p>
      </div>
      <Tabs
        items={sections.map((section) => ({
          id: section.id,
          label: section.label,
          content: <EmptyState title={`${section.label}: в работе`} description={section.description} />,
        }))}
      />
    </div>
  );
}
