import { Badge } from "@/components/ui/badge";

export type Status = "kept" | "changed" | "lost" | "new" | "moved" | "created" | "abolished" | "transformed";

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

export function StatusBadge({ status }: { status: Status }) {
  const { label, variant } = statusLabels[status];
  return <Badge variant={variant}>{label}</Badge>;
}
