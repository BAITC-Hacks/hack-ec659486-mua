"""Прогон тестового комплекта (редакции 8 → 9) напрямую через pipeline.run_pipeline.

Без API и без таймаута S16: живой прогон S15 с записью фикстур идёт дольше 180 с.

Запись фикстур (S15, ключ в .env этого worktree):
    cd backend && LLM_MODE=live LLM_RECORD_MOCKS=1 uv run python ../scripts/ops/demo_run.py
Таймаут одного запроса к модели здесь — LLM_TIMEOUT_S (по умолчанию 240 с): крупные запросы
извлечения функций не укладываются в 40 с из app/llm.py. Меняется только в этом процессе.
Продолжение оборванной записи: LLM_REUSE_RECORDED=1 — ответы, уже записанные в этом worktree
(файлы mocks/, изменённые или новые по git), берутся из файлов, к модели идут только недостающие.
Проверка на фикстурах, без обращения к модели:
    cd backend && LLM_MODE=mock uv run python ../scripts/ops/demo_run.py

Код выхода 0 — только при итоге done.
"""

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app import llm as llm_module  # noqa: E402
from app import pipeline, store  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.llm import LLM, MOCKS_DIR  # noqa: E402
from app.routers.runs import DEMO_AFTER, DEMO_BEFORE, _data_dir, _now_iso  # noqa: E402
from app.schemas import Report, RunStatus, empty_stats  # noqa: E402

REUSED: Counter[str] = Counter()
ASKED: Counter[str] = Counter()


def _recorded_here() -> set[Path]:
    """Фикстуры, записанные в этом worktree и ещё не закоммиченные: изменённые и новые файлы."""
    out = subprocess.run(
        ["git", "status", "--porcelain", "-uall", "--", str(MOCKS_DIR)],
        capture_output=True,
        text=True,
        check=True,
        cwd=MOCKS_DIR,
    ).stdout
    root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=MOCKS_DIR,
        ).stdout.strip()
    )
    return {(root / line[3:]).resolve() for line in out.splitlines() if line.endswith(".json")}


def _reuse_recorded() -> None:
    """Ответ, уже записанный в этом прогоне, — из файла; путь считается так же, как в модулях:
    mocks/<вызов>/sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True))[:16].json."""
    recorded = _recorded_here()
    ask_model = LLM.complete_json

    def complete_json(self, name, system, user, schema, **kwargs):  # type: ignore[no-untyped-def]
        try:
            raw = json.dumps(json.loads(user), ensure_ascii=False, sort_keys=True)
        except ValueError:
            raw = None
        if raw is not None:
            path = MOCKS_DIR / name / f"{hashlib.sha256(raw.encode()).hexdigest()[:16]}.json"
            if path.resolve() in recorded:
                REUSED[name] += 1
                return json.loads(path.read_text(encoding="utf-8"))
        ASKED[name] += 1
        return ask_model(self, name=name, system=system, user=user, schema=schema, **kwargs)

    LLM.complete_json = complete_json  # type: ignore[method-assign]
    print(f"продолжение записи: в этом worktree уже записано {len(recorded)} ответов", flush=True)


def main() -> int:
    llm_module.REQUEST_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_S", "240"))
    if os.environ.get("LLM_REUSE_RECORDED") == "1":
        _reuse_recorded()
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
    print(
        f"режим LLM: {get_settings().llm_mode}; таймаут запроса "
        f"{llm_module.REQUEST_TIMEOUT_SECONDS:.0f} с; запуск {run_id}…",
        flush=True,
    )
    started = time.monotonic()
    asyncio.run(pipeline.run_pipeline(run_id))
    record = store.get(run_id)
    assert record is not None
    st, rep = record.status, record.report
    print(f"итог: {st.status} за {time.monotonic() - started:.0f} с")
    if REUSED or ASKED:
        print(f"из записанного: {dict(REUSED)}; спрошено у модели: {dict(ASKED)}")
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
