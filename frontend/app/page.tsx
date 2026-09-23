import Link from "next/link";

import { EmptyState } from "@/components/ui/empty-state";

export default function HomePage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium text-primary">Шаг 1 · Документы</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Сравнение редакций</h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          Загрузите документы до и после реорганизации или выберите тестовый комплект.
        </p>
      </div>
      <EmptyState
        title="Загрузка документов в работе"
        description="Скоро здесь появятся поля для двух комплектов документов и кнопка запуска анализа."
      />
      <Link href="/report/demo" className="inline-flex rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted">
        Перейти к экрану отчёта
      </Link>
    </div>
  );
}
