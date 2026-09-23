import "./globals.css";

import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { HealthBadge } from "@/components/health-badge";

const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || "ОргДифф";

export const metadata: Metadata = {
  title: {
    default: APP_NAME,
    template: `%s · ${APP_NAME}`,
  },
  description: "Каркас хакатона: FastAPI + Next.js, OpenAI с mock-режимом.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ru">
      <body className="min-h-screen bg-background text-foreground antialiased">
        <header className="border-b border-border bg-card">
          <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4 px-4 py-3">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              {APP_NAME}
            </Link>
            <HealthBadge />
          </div>
        </header>
        <main className="mx-auto w-full max-w-5xl px-4 py-8">{children}</main>
        <footer className="mx-auto w-full max-w-5xl px-4 py-6 text-xs text-muted-foreground">
          {APP_NAME} · каркас без доменной логики · MIT
        </footer>
      </body>
    </html>
  );
}
