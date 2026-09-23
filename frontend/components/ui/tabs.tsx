"use client";

import { useId, useState, type ReactNode } from "react";

export interface TabItem {
  id: string;
  label: string;
  content: ReactNode;
}

export function Tabs({ items }: { items: readonly TabItem[] }) {
  const [selectedId, setSelectedId] = useState(items[0]?.id ?? "");
  const prefix = useId();
  const selected = items.find((item) => item.id === selectedId) ?? items[0];

  if (!selected) return null;

  return (
    <div>
      <div role="tablist" aria-label="Разделы отчёта" className="flex flex-wrap gap-2 border-b border-border pb-3">
        {items.map((item) => (
          <button
            key={item.id}
            id={`${prefix}-tab-${item.id}`}
            type="button"
            role="tab"
            aria-selected={item.id === selected.id}
            aria-controls={`${prefix}-panel-${item.id}`}
            onClick={() => setSelectedId(item.id)}
            className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
              item.id === selected.id ? "bg-primary text-primary-foreground" : "hover:bg-muted"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div
        id={`${prefix}-panel-${selected.id}`}
        role="tabpanel"
        aria-labelledby={`${prefix}-tab-${selected.id}`}
        className="pt-6"
      >
        {selected.content}
      </div>
    </div>
  );
}
