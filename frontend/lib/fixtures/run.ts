/** GET /api/runs/{run_id}; status names and fields mirror S01. */
import type { RunStatus } from "@/lib/types";

export const demoRuns: RunStatus[] = [
  {
    "run_id": "demo-case11",
    "status": "parsing",
    "progress": 5,
    "detail": "Разбор документов",
    "missing_steps": []
  },
  {
    "run_id": "demo-case11",
    "status": "verification",
    "progress": 65,
    "detail": "Проверка сопоставлений",
    "missing_steps": []
  },
  {
    "run_id": "demo-case11",
    "status": "done",
    "progress": 100,
    "detail": null,
    "missing_steps": []
  }
];

export const parsingRun = demoRuns[0];
export const verificationRun = demoRuns[1];
export const doneRun = demoRuns[2];
export const runFixtures = { parsing: parsingRun, verification: verificationRun, done: doneRun };
export default runFixtures;
