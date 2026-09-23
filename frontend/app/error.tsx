"use client";

import { TriangleAlert } from "lucide-react";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { t } from "@/lib/i18n";

/** Граница ошибок App Router: показывает сообщение и кнопку «Повторить» вместо белого экрана. */
export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <EmptyState
      icon={<TriangleAlert className="size-8 text-danger" aria-hidden="true" />}
      title={t("error")}
      description={error.message || "Что-то пошло не так."}
      action={<Button onClick={reset}>{t("retry")}</Button>}
    />
  );
}
