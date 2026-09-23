"""Прогон тестового комплекта (редакции 8 → 9) напрямую через pipeline.run_pipeline.

Без API и без таймаута S16: живой прогон S15 с записью фикстур идёт дольше 180 с.

Запись фикстур (S15, ключ в .env этого worktree):
    cd backend && LLM_MODE=live LLM_RECORD_MOCKS=1 uv run python ../scripts/ops/demo_run.py
Проверка на фикстурах, без обращения к модели:
    cd backend && LLM_MODE=mock uv run python ../scripts/ops/demo_run.py

Код выхода 0 — только при итоге done.
"""

import asyncio
import sys
import time
from collections import Counter
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app import pipeline, store  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.routers.runs import DEMO_AFTER, DEMO_BEFORE, _data_dir, _now_iso  # noqa: E402
from app.schemas import Report, RunStatus, empty_stats  # noqa: E402


def main() -> int:
    data = _data_dir() / "case11"
    run_id = f"demo-{uuid4().hex[:8]}"
    inputs = {
        "before": [{"path": str(data / DEMO_BEFORE), "name": DEMO_BEFORE}],
        "after": [{"path": str(data / DEMO_AFTER), "name": DEMO_AFTER}],
    }
    status = RunStatus(
        run_id=run_id, status="queued", progress=0, detail="demo_run.py", missing_steps=[]
    )
    empty = Report(
        run_id=run_id,
        created_at=_now_iso(),
        before_documents=[],
        after_documents=[],
        unit_changes=[],
        function_matches=[],
        duplicates=[],
        conflicts=[],
        constraints=[],
        conclusion_md="",
        recommendations=[],
        stats=empty_stats(),
    )
    store.put(run_id, store.RunRecord(status=status, report=empty, inputs=inputs))
    print(f"режим LLM: {get_settings().llm_mode}; запуск {run_id}…", flush=True)
    started = time.monotonic()
    asyncio.run(pipeline.run_pipeline(run_id))
    record = store.get(run_id)
    assert record is not None
    st, rep = record.status, record.report
    print(f"итог: {st.status} за {time.monotonic() - started:.0f} с")
    print(f"не выполнены шаги: {', '.join(st.missing_steps) or '—'}")
    print(f"detail: {st.detail}")
    if st.status in ("done", "partial"):
        units = Counter(c.status for c in rep.unit_changes)
        matches = Counter(f"{m.status}{'' if m.verified else '?'}" for m in rep.function_matches)
        print(f"подразделения: {len(rep.unit_changes)} {dict(units)}")
        print(f"функции (? — требует проверки): {dict(sorted(matches.items()))}")
        dups = sum(d.verified for d in rep.duplicates)
        conflicts = sum(c.verified for c in rep.conflicts)
        print(
            f"дубли: {len(rep.duplicates)}, подтверждено {dups}; "
            f"конфликты: {len(rep.conflicts)}, подтверждено {conflicts}; "
            f"ограничения: {len(rep.constraints)}"
        )
        print(f"заключение: {rep.conclusion_md[:200]!r}")
    return 0 if st.status == "done" else 1


if __name__ == "__main__":
    sys.exit(main())
