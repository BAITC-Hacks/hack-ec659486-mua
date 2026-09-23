import "./globals.css";

import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { HealthBadge } from "@/components/health-badge";

export const metadata: Metadata = {
  title: {
    default: "ОргДифф",
    template: "%s · ОргДифф",
  },
  description: "Анализ изменений оргструктуры и функций с указанием пунктов документов.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ru">
      <body className="min-h-screen bg-background text-foreground antialiased">
        <header className="border-b border-border bg-card">
          <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6">
            <div className="min-w-0">
              <Link href="/" className="text-xl font-semibold tracking-tight text-foreground">
                ОргДифф
              </Link>
              <p className="mt-0.5 text-sm text-muted-foreground">
                Анализ оргструктуры и функционала
              </p>
            </div>
            <HealthBadge />
          </div>
          <nav aria-label="Основная навигация" className="mx-auto flex max-w-6xl gap-2 px-4 pb-3 sm:px-6">
            <Link href="/" className="rounded-lg px-3 py-2 text-sm font-medium hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
              Загрузка
            </Link>
            <Link href="/report/demo" className="rounded-lg px-3 py-2 text-sm font-medium hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
              Отчёт
            </Link>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">{children}</main>
        <footer className="mx-auto w-full max-w-6xl border-t border-border px-4 py-5 text-sm text-muted-foreground sm:px-6">
          Выводы рекомендательные. Каждый вывод сопровождается ссылкой на пункт документа.
        </footer>
      </body>
    </html>
  );
}
