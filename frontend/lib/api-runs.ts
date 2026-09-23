import { api } from "@/lib/api";
import type { Clause, Report, RunCreated, RunStatus } from "@/lib/types";

export function createRun(before: File[], after: File[]): Promise<RunCreated> {
  const body = new FormData();
  before.forEach((file) => body.append("before[]", file));
  after.forEach((file) => body.append("after[]", file));
  return api<RunCreated>("/api/runs", { method: "POST", body });
}

export function createDemoRun(): Promise<RunCreated> {
  return api<RunCreated>("/api/runs/demo", { method: "POST" });
}

export function getRun(id: string): Promise<RunStatus> {
  return api<RunStatus>(`/api/runs/${encodeURIComponent(id)}`, { cache: "no-store" });
}

export function getReport(id: string): Promise<Report> {
  return api<Report>(`/api/runs/${encodeURIComponent(id)}/report`, { cache: "no-store" });
}

export function getClause(runId: string, docId: string, clauseNumber: string): Promise<Clause> {
  return api<Clause>(`/api/runs/${encodeURIComponent(runId)}/clauses/${encodeURIComponent(docId)}/${encodeURIComponent(clauseNumber)}`, { cache: "no-store" });
}

export function useFixtures(): boolean {
  return process.env.NEXT_PUBLIC_USE_FIXTURES === "1";
}
