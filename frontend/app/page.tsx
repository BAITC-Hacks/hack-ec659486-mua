"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { UploadBox } from "@/components/upload-box";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { createDemoRun, createRun } from "@/lib/api-runs";

const MAX_TOTAL_FILES = 10;

export default function HomePage() {
  const router = useRouter();
  const [before, setBefore] = useState<File[]>([]);
  const [after, setAfter] = useState<File[]>([]);
  const [pending, setPending] = useState<"upload" | "demo" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const submitting = useRef(false);
  const totalFiles = before.length + after.length;
  const exceedsTotalLimit = totalFiles > MAX_TOTAL_FILES;
  const canAnalyze = before.length > 0 && after.length > 0 && !exceedsTotalLimit;

  async function startRun(mode: "upload" | "demo") {
    if (submitting.current || (mode === "upload" && !canAnalyze)) return;
    submitting.current = true;
    setPending(mode);
    setError(null);

    try {
      const { run_id } = mode === "demo" ? await createDemoRun() : await createRun(before, after);
      router.push(`/runs/${encodeURIComponent(run_id)}`);
    } catch (cause) {
      setError(cause instanceof ApiError
        ? `${cause.message}${cause.status === 0 ? ". Проверьте, запущен ли backend на :8000." : ""}`
        : "Не удалось запустить анализ. Попробуйте ещё раз.");
      submitting.current = false;
      setPending(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium text-primary">Шаг 1 · Документы</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Сравнение редакций</h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          Загрузите документы до и после реорганизации или выберите тестовый комплект.
        </p>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <UploadBox label="До реорганизации" files={before} onChange={setBefore} disabled={pending !== null} />
        <UploadBox label="После реорганизации" files={after} onChange={setAfter} disabled={pending !== null} />
      </div>

      {exceedsTotalLimit ? (
        <p id="total-files-error" role="alert" className="rounded-lg border border-danger/30 bg-danger/5 p-4 text-sm text-danger">
          Выбрано файлов: {totalFiles}. Для анализа можно отправить не более {MAX_TOTAL_FILES} файлов
          суммарно в комплектах «до» и «после». Уберите лишние файлы, чтобы продолжить.
        </p>
      ) : null}

      {error ? (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger/5 p-4 text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center">
        <Button
          size="lg"
          disabled={!canAnalyze || pending !== null}
          aria-describedby={exceedsTotalLimit ? "total-files-error" : "upload-requirements"}
          loading={pending === "upload"}
          onClick={() => void startRun("upload")}
        >
          {pending === "upload" ? "Отправляем документы…" : "Проанализировать"}
        </Button>
        <p id="upload-requirements" className="text-sm text-muted-foreground">
          Добавьте хотя бы один документ в каждый комплект. Не более {MAX_TOTAL_FILES} файлов суммарно
          в «до» и «после».
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Попробуйте на готовых документах</CardTitle>
          <CardDescription>Тестовый комплект: редакции 8 и 9 Положения о внутреннем аудите.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="secondary"
            disabled={pending !== null}
            loading={pending === "demo"}
            onClick={() => void startRun("demo")}
          >
            {pending === "demo" ? "Запускаем тестовый комплект…" : "Тестовый комплект"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
