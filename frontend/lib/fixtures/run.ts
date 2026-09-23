/** GET /api/runs/{run_id}, spec §4; fallback while s/contract is unavailable. */
export interface RunStatus {
  status: "queued" | "parsing" | "units" | "functions" | "matching" | "conclusion" | "done" | "error";
  progress: number;
  error?: string | null;
}

export const demoRuns: RunStatus[] = [
  {
    "status": "parsing",
    "progress": 20,
    "error": null
  },
  {
    "status": "matching",
    "progress": 70,
    "error": null
  },
  {
    "status": "done",
    "progress": 100,
    "error": null
  }
];

export const parsingRun = demoRuns[0];
export const matchingRun = demoRuns[1];
export const doneRun = demoRuns[2];
export const runFixtures = { parsing: parsingRun, matching: matchingRun, done: doneRun };
export default runFixtures;
