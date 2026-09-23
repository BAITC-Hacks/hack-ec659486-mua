import { Badge } from "@/components/ui/badge";

export type Status = "kept" | "changed" | "lost" | "new" | "moved" | "created" | "abolished" | "transformed";
export type Verification = "exact" | "lexical" | "llm";

const statusLabels: Record<Status, { label: string; variant: "success" | "warning" | "danger" | "default" }> = {
  kept: { label: "Сохранена", variant: "success" },
  changed: { label: "Изменена", variant: "warning" },
  lost: { label: "Утрачена", variant: "danger" },
  new: { label: "Новая", variant: "default" },
  moved: { label: "Перенесена", variant: "warning" },
  created: { label: "Создано", variant: "default" },
  abolished: { label: "Упразднено", variant: "danger" },
  transformed: { label: "Преобразовано", variant: "warning" },
};

const verificationLabels: Record<Verification, string> = {
  exact: "Дословно",
  lexical: "По тексту",
  llm: "Проверено моделью",
};

export function StatusBadge({
  status,
  verified,
  verification,
}: {
  status: Status;
  verified?: boolean;
  verification?: Verification;
}) {
  const { label, variant } = statusLabels[status];
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <Badge variant={variant}>{label}</Badge>
      {verification ? <Badge variant="muted">{verificationLabels[verification]}</Badge> : null}
      {verified === false ? <Badge variant="warning">Требует проверки</Badge> : null}
    </span>
  );
}
