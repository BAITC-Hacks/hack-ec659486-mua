import type { Metadata } from "next";
import Link from "next/link";

import { ExampleForm } from "@/components/example-form";
import { t } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "Пример вызова LLM",
};

/** Серверная обёртка страницы; вся интерактивность — в клиентском ExampleForm. */
export default function ExamplePage() {
  return (
    <div className="space-y-6">
      <div>
        <Link href="/" className="text-sm text-muted-foreground hover:underline">
          ← {t("back")}
        </Link>
        <h1 className="mt-2 text-2xl font-bold tracking-tight">Пример вызова LLM</h1>
        <p className="mt-1 text-muted-foreground">
          Образец экрана: скопируйте <code>components/example-form.tsx</code> и{" "}
          <code>app/example/page.tsx</code> для новой фичи.
        </p>
      </div>
      <ExampleForm />
    </div>
  );
}
