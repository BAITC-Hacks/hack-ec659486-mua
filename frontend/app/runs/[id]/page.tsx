import { EmptyState } from "@/components/ui/empty-state";

export default function RunPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium text-primary">Шаг 2 · Анализ</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Ход анализа</h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          Здесь появится прогресс разбора документов, сопоставления подразделений и функций.
        </p>
      </div>
      <EmptyState title="Экран прогресса в работе" description="Статус анализа появится после запуска тестового комплекта или загрузки документов." />
    </div>
  );
}
