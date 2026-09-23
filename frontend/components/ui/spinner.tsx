import { LoaderCircle } from "lucide-react";

import { cn } from "@/lib/utils";

export interface SpinnerProps {
  className?: string;
  /** Текст для скринридеров. */
  label?: string;
}

export function Spinner({ className, label = "Загрузка" }: SpinnerProps) {
  return (
    <LoaderCircle
      role="status"
      aria-label={label}
      className={cn("size-5 animate-spin text-muted-foreground", className)}
    />
  );
}
