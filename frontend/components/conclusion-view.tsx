"use client";

import { Fragment, type ReactNode } from "react";
import { EmptyState } from "@/components/ui/empty-state";
import { SourceButtons, type SourceHandler } from "@/components/units-table";
import type { Source } from "@/lib/types";

function bold(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={index}>{part.slice(2, -2)}</strong> : <Fragment key={index}>{part}</Fragment>);
}

export function ConclusionView({ conclusion_md, run_id, sources = [], onSource }: {
  conclusion_md: string; run_id: string; sources?: Source[]; onSource: SourceHandler;
}) {
  function references(text: string) {
    const numbers = new Set(text.match(/\d+(?:\.\d+)+/g) ?? []);
    const referenced = sources.filter((source) => source.clause_number !== null && numbers.has(source.clause_number));
    return <div className="mt-2 space-y-2">{(["before", "after"] as const).map((version) => {
      const items = referenced.filter((source) => source.version === version);
      return items.length ? <div key={version} className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">{version === "before" ? "До" : "После"}</span>
        <SourceButtons sources={items} onSource={onSource} />
      </div> : null;
    })}</div>;
  }

  const blocks: ReactNode[] = [];
  const lines = conclusion_md.replace(/\r\n/g, "\n").split("\n");
  for (let index = 0; index < lines.length;) {
    const line = lines[index].trim();
    if (!line) { index++; continue; }
    const heading = /^(#{1,6})\s+(.+)$/.exec(line);
    if (heading) {
      const Heading = `h${Math.min(heading[1].length + 1, 6)}` as "h2" | "h3" | "h4" | "h5" | "h6";
      blocks.push(<Heading key={index} className="text-xl font-semibold">{bold(heading[2])}</Heading>);
      index++;
      continue;
    }
    const list = /^(\d+\.|[-*])\s+(.+)$/.exec(line);
    if (list) {
      const ordered = /^\d/.test(list[1]);
      const start = index;
      const items: ReactNode[] = [];
      while (index < lines.length) {
        const item = /^(\d+\.|[-*])\s+(.+)$/.exec(lines[index].trim());
        if (!item || /^\d/.test(item[1]) !== ordered) break;
        items.push(<li key={index} className="pl-1">{bold(item[2])}{references(item[2])}</li>);
        index++;
      }
      blocks.push(ordered ? <ol key={start} start={parseInt(list[1], 10)} className="list-decimal space-y-4 pl-6">{items}</ol>
        : <ul key={start} className="list-disc space-y-4 pl-6">{items}</ul>);
      continue;
    }
    const start = index;
    const paragraph: string[] = [];
    while (index < lines.length && lines[index].trim() && !/^(#{1,6}\s|\d+\.\s|[-*]\s)/.test(lines[index].trim())) {
      paragraph.push(lines[index++].trim());
    }
    const text = paragraph.join(" ");
    blocks.push(<div key={start}><p>{bold(text)}</p>{references(text)}</div>);
  }

  return <section className="space-y-6">
    <a href={`/api/runs/${encodeURIComponent(run_id)}/report.md`} download
      className="inline-flex rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
      Скачать заключение (.md)
    </a>
    {blocks.length ? <div className="max-w-4xl space-y-5 leading-relaxed">{blocks}</div> : <EmptyState title="Заключение пока не сформировано" />}
  </section>;
}
