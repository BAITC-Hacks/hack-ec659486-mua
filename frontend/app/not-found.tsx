import Link from "next/link";

import { EmptyState } from "@/components/ui/empty-state";
import { t } from "@/lib/i18n";

export default function NotFound() {
  return (
    <EmptyState
      title={t("notFound")}
      description="Проверьте адрес или вернитесь на главную."
      action={
        <Link href="/" className="text-sm font-medium text-primary underline-offset-4 hover:underline">
          {t("home")}
        </Link>
      }
    />
  );
}
