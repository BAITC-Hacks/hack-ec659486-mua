"use client";

import { type FormEvent, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { postJson } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { ExampleRequest, ExampleResponse } from "@/lib/types";

/**
 * Шаблон клиентского компонента «форма → API → результат» с состояниями
 * loading / error / result. Скопируйте для новой фичи и замените типы и путь.
 */
export function ExampleForm() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExampleResponse | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const body: ExampleRequest = { text: text.trim() };
      const response = await postJson<ExampleResponse>("/api/example", body);
      setResult(response);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : t("error"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>POST /api/example</CardTitle>
        <CardDescription>
          Текст уходит в LLM со strict JSON-схемой. Без ключа OpenAI ответ берётся из
          backend/app/mocks/example.json.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-3">
          <label htmlFor="example-text" className="block text-sm font-medium">
            Текст запроса
          </label>
          <textarea
            id="example-text"
            name="text"
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={3}
            maxLength={4000}
            required
            placeholder="Например: коротко объясни, что такое каркас проекта"
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
          />
          <div className="flex items-center gap-3">
            <Button type="submit" loading={loading} disabled={!text.trim()}>
              {t("submit")}
            </Button>
            {error ? (
              <Button type="button" variant="ghost" size="sm" onClick={() => setError(null)}>
                {t("cancel")}
              </Button>
            ) : null}
          </div>
        </form>

        {error ? (
          <p role="alert" className="mt-4 rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
            {t("error")}: {error}
          </p>
        ) : null}

        {result ? (
          <div className="mt-4 rounded-lg bg-muted p-4 text-sm">
            <div className="mb-2 flex items-center gap-2 text-muted-foreground">
              <span>Ответ</span>
              <Badge variant={result.llm_mode === "live" ? "default" : "warning"}>
                {result.llm_mode}
              </Badge>
            </div>
            <p className="whitespace-pre-wrap">{result.answer}</p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
