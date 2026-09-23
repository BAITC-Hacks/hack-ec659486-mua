"""P4a «Кандидаты» (spec §2 P4a, §2а): гибридный поиск кандидатов, без статусов.

Что делает модуль:
- `tokenize` — нижний регистр, ё→е; коды и аббревиатуры (БВА, ДЗО, СВА, ИТ) и номера («2.3.»)
  остаются отдельными токенами как есть, остальные слова — грубая основа (окончание отсекается
  у слов длиннее 5 букв), стоп-слова выбрасываются;
- лексический ранг — BM25 (k1 = 1.5, b = 0.75, idf по корпусу, в котором ищем) на numpy;
- ранг по сигнатуре — равенство `Function.signature` (порядок внутри группы — по BM25);
- dense-ранг (опционально) — косинус векторов `text-embedding-3-small` из кэша
  `mocks/embeddings/{sha256(text)}.json`; без кэша и без ключа dense просто пропускается;
- три ранга сливаются RRF: `score = Σ 1/(60 + rank)`; точное совпадение нормализованного
  текста — отдельный кандидат `reasons = ["exact"]`, `score = inf`, всегда первым.

Похожесть здесь ничего не решает: порога нет ни у BM25, ни у косинуса (0,85 давал 44 ложных
дубля из 150), сигнатура путает «аудит ИТ» и «аудит закупок». Статус ставит только проверка
(`app.matching.verify_matches`, S11 `verify_duplicates`).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from app.llm import LLM, MOCKS_DIR, redact_secrets
from app.schemas import Function

logger = logging.getLogger(__name__)

TOP_K = 5
POOL = 20  # глубина каждого ранга перед слиянием RRF
RRF_K = 60
BM25_K1 = 1.5
BM25_B = 0.75
EMBED_MODEL = "text-embedding-3-small"
EMBED_BATCH = 100
EMBEDDINGS_DIR = MOCKS_DIR / "embeddings"

Reason = Literal["exact", "lexical", "signature", "dense"]
_REASON_ORDER: tuple[Reason, ...] = ("exact", "lexical", "signature", "dense")


@dataclass
class Candidate:
    """Кандидат «после» для функции «до» (или пара для дубля): ранг, не решение."""

    after_id: str
    score: float
    reasons: list[Reason] = field(default_factory=list)


# --- Лексика --------------------------------------------------------------------------------

STOP_WORDS = frozenset(
    "и в во на по с со для о об а к ко из от до при за или также том числе т ч".split()
)
# Грубая основа: окончание отсекается у слов длиннее 5 букв, основа не короче 4 букв.
# «-ок/-ки/-ка» (проверок/проверки/проверка) сводятся к одной основе «провер».
_ENDINGS = tuple(
    sorted(
        (
            "ками ках кам кой ки ка ку ке ок "
            "иями ями ами ого его ому ему ыми ими ией иям иях ую юю ая яя ое ее ые ие ый ий "
            "ой ей ом ем ам ям ах ях ов ев ых их ым им ию ия ии ью "
            "ует уют ают яют ает яет ить ать ять еть ет ют ут ит ат ят ть "
            "а я о е ы и у ю ь й"
        ).split(),
        key=len,
        reverse=True,
    )
)
_MIN_STEM = 4
_WORD_RE = re.compile(r"\d+(?:\.\d+)*\.?|[A-Za-zА-Яа-яЁё0-9]+")
_ABBR_RE = re.compile(r"^[A-ZА-ЯЁ][A-ZА-ЯЁ0-9]{1,7}$")
_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)*\.?$")
_LEADING_ENUM_RE = re.compile(r"^\s*(?:\d+(?:\.\d+)*\.?|[а-яa-z]\))\s+", re.IGNORECASE)


def stem(word: str) -> str:
    """Грубая основа слова в нижнем регистре (без морфологии: только для ранжирования)."""
    if len(word) <= 5:
        return word
    if word.endswith(("ся", "сь")) and len(word) - 2 >= _MIN_STEM:
        word = word[:-2]
    for ending in _ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= _MIN_STEM:
            return word[: -len(ending)]
    return word


def tokenize(text: str) -> list[str]:
    """Токены для BM25: коды, аббревиатуры и номера — как есть; слова — грубая основа."""
    tokens: list[str] = []
    for raw in _WORD_RE.findall(text or ""):
        if _NUMBER_RE.match(raw):
            tokens.append(raw.rstrip("."))
            continue
        is_abbr = bool(_ABBR_RE.match(raw))
        word = raw.lower().replace("ё", "е")
        if is_abbr:
            tokens.append(word)
            continue
        if word in STOP_WORDS or len(word) < 2:
            continue
        tokens.append(stem(word))
    return tokens


def normalize_text(text: str) -> str:
    """Ключ точного совпадения: нижний регистр, ё→е, без нумерации, пунктуации и лишних пробелов."""
    value = (text or "").lower().replace("ё", "е")
    value = _LEADING_ENUM_RE.sub("", value)
    value = re.sub(r"[^\w\s]|_", " ", value)
    return re.sub(r"\s+", " ", value).strip()


class BM25:
    """BM25 на numpy: матрица весов «документ × термин», запрос — сумма столбцов."""

    def __init__(self, docs: Sequence[Sequence[str]], k1: float = BM25_K1, b: float = BM25_B):
        self.vocab: dict[str, int] = {}
        for tokens in docs:
            for token in tokens:
                self.vocab.setdefault(token, len(self.vocab))
        n_docs, n_terms = len(docs), len(self.vocab)
        self.size = n_docs
        tf = np.zeros((n_docs, max(n_terms, 1)), dtype=np.float64)
        for i, tokens in enumerate(docs):
            for token in tokens:
                tf[i, self.vocab[token]] += 1.0
        lengths = tf.sum(axis=1)
        avgdl = float(lengths.mean()) if n_docs and lengths.mean() > 0 else 1.0
        df = (tf > 0).sum(axis=0)
        idf = np.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
        norm = k1 * (1.0 - b + b * lengths[:, None] / avgdl)
        with np.errstate(divide="ignore", invalid="ignore"):
            weights = np.where(tf > 0, tf * (k1 + 1.0) / (tf + norm), 0.0)
        self.weights = weights * idf[None, :]

    def scores(self, query: Sequence[str]) -> np.ndarray:
        columns = sorted({self.vocab[t] for t in query if t in self.vocab})
        if not columns or not self.size:
            return np.zeros(self.size, dtype=np.float64)
        return self.weights[:, columns].sum(axis=1)

    def top(self, query: Sequence[str], k: int) -> list[tuple[int, float]]:
        """Индексы с положительной оценкой, по убыванию (при равенстве — по порядку корпуса)."""
        scores = self.scores(query)
        order = sorted((i for i in range(self.size) if scores[i] > 0), key=lambda i: -scores[i])
        return [(i, float(scores[i])) for i in order[:k]]


# --- Dense (опционально) ----------------------------------------------------------------------


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_cached_vector(sha: str) -> np.ndarray | None:
    path = EMBEDDINGS_DIR / f"{sha}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("model") != EMBED_MODEL or data.get("text_sha256") != sha:
            return None
        vector = np.asarray(data["vector"], dtype=np.float64)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("embeddings: кэш %s не читается (%s), dense пропущен", path.name, exc)
        return None
    return vector if vector.ndim == 1 and vector.size else None


def _write_cached_vector(sha: str, vector: list[float]) -> None:
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"model": EMBED_MODEL, "text_sha256": sha, "vector": vector}
    (EMBEDDINGS_DIR / f"{sha}.json").write_text(json.dumps(payload), encoding="utf-8")


def _can_fetch(llm: LLM | None) -> bool:
    if llm is None:
        return False
    try:
        return llm.mode == "live" and bool(llm.settings.openai_api_key)
    except AttributeError:
        return False


def embed(texts: list[str], llm: LLM | None = None) -> list[np.ndarray | None]:
    """Векторы текстов: кэш → (live с ключом) OpenAI embeddings → иначе None без ошибки."""
    out: list[np.ndarray | None] = [None] * len(texts)
    missing: dict[str, str] = {}  # text → sha
    for i, text in enumerate(texts):
        if not text or not text.strip():
            continue
        sha = _sha256(text)
        out[i] = _read_cached_vector(sha)
        if out[i] is None:
            missing[text] = sha
    if not missing or not _can_fetch(llm):
        return out
    fetched: dict[str, np.ndarray] = {}
    pending = list(missing)
    try:
        client = llm._get_client()  # type: ignore[union-attr]
        for start in range(0, len(pending), EMBED_BATCH):
            batch = pending[start : start + EMBED_BATCH]
            response = client.embeddings.create(model=EMBED_MODEL, input=batch)
            for text, item in zip(batch, response.data, strict=True):
                vector = [float(x) for x in item.embedding]
                _write_cached_vector(missing[text], vector)
                fetched[text] = np.asarray(vector, dtype=np.float64)
    except Exception as exc:  # dense опционален: любая ошибка — только пропуск ранга
        logger.warning(
            "embeddings: запрос не удался (%s), dense пропущен: %s",
            type(exc).__name__,
            redact_secrets(str(exc)),
        )
    for i, text in enumerate(texts):
        if out[i] is None and text in fetched:
            out[i] = fetched[text]
    return out


def _unit_matrix(vectors: list[np.ndarray | None]) -> tuple[np.ndarray | None, list[int]]:
    """Нормированные векторы корпуса (только имеющиеся) и их индексы в корпусе."""
    present = [i for i, v in enumerate(vectors) if v is not None]
    if not present:
        return None, []
    dims = {vectors[i].size for i in present}  # type: ignore[union-attr]
    if len(dims) != 1:
        logger.warning("embeddings: векторы разной размерности, dense пропущен")
        return None, []
    matrix = np.vstack([vectors[i] for i in present])
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms, present


# --- Гибридный ранг ---------------------------------------------------------------------------


def _usable_signature(signature: str | None) -> str | None:
    """Сигнатура без объекта («КЛАСС|») слишком общая даже для кандидата."""
    if not signature or "|" not in signature:
        return None
    verb, _, obj = signature.partition("|")
    return signature if verb and obj.strip() else None


class _Index:
    """Корпус для поиска: токены, BM25, точные ключи, сигнатуры, векторы (если есть)."""

    def __init__(
        self,
        texts: list[str],
        signatures: list[str | None],
        vectors: list[np.ndarray | None] | None = None,
    ) -> None:
        self.texts = texts
        self.tokens = [tokenize(t) for t in texts]
        self.bm25 = BM25(self.tokens)
        self.exact: dict[str, list[int]] = {}
        for i, text in enumerate(texts):
            key = normalize_text(text)
            if key:
                self.exact.setdefault(key, []).append(i)
        self.by_signature: dict[str, list[int]] = {}
        for i, sig in enumerate(signatures):
            usable = _usable_signature(sig)
            if usable:
                self.by_signature.setdefault(usable, []).append(i)
        self.matrix, self.present = _unit_matrix(vectors or [None] * len(texts))

    def rank(
        self,
        text: str,
        signature: str | None,
        vector: np.ndarray | None,
        k: int,
        allowed: Callable[[int], bool] = lambda _i: True,
    ) -> list[tuple[int, float, list[Reason]]]:
        """Top-k индексов корпуса: сначала точные совпадения, затем RRF трёх рангов."""
        exact = [i for i in self.exact.get(normalize_text(text), []) if allowed(i)]
        exact_set = set(exact)
        result: list[tuple[int, float, list[Reason]]] = [(i, math.inf, ["exact"]) for i in exact]
        if len(result) >= k:
            return result[:k]

        scores = self.bm25.scores(tokenize(text))
        lexical = sorted(
            (
                i
                for i in range(self.bm25.size)
                if scores[i] > 0 and i not in exact_set and allowed(i)
            ),
            key=lambda i: -scores[i],
        )[:POOL]
        usable = _usable_signature(signature)
        by_sig = sorted(
            (
                i
                for i in self.by_signature.get(usable or "", [])
                if i not in exact_set and allowed(i)
            ),
            key=lambda i: -scores[i],
        )[:POOL]
        dense: list[int] = []
        if vector is not None and self.matrix is not None and vector.size == self.matrix.shape[1]:
            q_norm = float(np.linalg.norm(vector)) or 1.0
            cosines = self.matrix @ (vector / q_norm)
            order = sorted(range(len(self.present)), key=lambda j: -cosines[j])
            dense = [
                self.present[j]
                for j in order
                if self.present[j] not in exact_set and allowed(self.present[j])
            ][:POOL]

        fused: dict[int, float] = {}
        reasons: dict[int, list[Reason]] = {}
        for name, ranking in (("lexical", lexical), ("signature", by_sig), ("dense", dense)):
            for rank, i in enumerate(ranking, start=1):
                fused[i] = fused.get(i, 0.0) + 1.0 / (RRF_K + rank)
                reasons.setdefault(i, []).append(name)  # type: ignore[arg-type]
        order = sorted(fused, key=lambda i: (-fused[i], i))
        for i in order[: k - len(result)]:
            ordered = [r for r in _REASON_ORDER if r in reasons[i]]
            result.append((i, round(fused[i], 6), ordered))
        return result


def _vectors(texts: list[str], llm: LLM | None) -> list[np.ndarray | None]:
    try:
        return embed(texts, llm)
    except Exception as exc:  # pragma: no cover - embed сам гасит ошибки; страховка
        logger.warning("embeddings: dense пропущен (%s)", type(exc).__name__)
        return [None] * len(texts)


def rank_candidates(
    queries: list[Function], corpus: list[Function], llm: LLM | None = None, k: int = TOP_K
) -> dict[str, list[Candidate]]:
    """Для каждой функции `queries` — до k кандидатов из `corpus` (в обе стороны: до↔после)."""
    if not queries:
        return {}
    if not corpus:
        return {fn.id: [] for fn in queries}
    vectors = _vectors([f.text for f in corpus] + [f.text for f in queries], llm)
    index = _Index([f.text for f in corpus], [f.signature for f in corpus], vectors[: len(corpus)])
    result: dict[str, list[Candidate]] = {}
    for fn, vector in zip(queries, vectors[len(corpus) :], strict=True):
        ranked = index.rank(fn.text, fn.signature, vector, k)
        result[fn.id] = [Candidate(corpus[i].id, score, reasons) for i, score, reasons in ranked]
    return result


def find_candidates(
    before: list[Function], after: list[Function], llm: LLM | None = None, k: int = TOP_K
) -> dict[str, list[Candidate]]:
    """Для каждой функции «до» — до k кандидатов среди ВСЕХ функций «после» (без запретов)."""
    before = [fn for fn in before if fn.modality != "prohibition"]
    after = [fn for fn in after if fn.modality != "prohibition"]
    return rank_candidates(before, after, llm, k)


# --- Кандидаты дублей -------------------------------------------------------------------------

TEMPLATE_PHRASES: tuple[str, ...] = (
    "иные функции",
    "поручения руководства",
    "согласно законодательству",
    "в пределах компетенции",
)
_TEMPLATE_RES = (
    re.compile(r"\bин(?:ые|ых|ыми|ую|ой)\s+(?:функци|обязанност|задач|полномочи)\w*"),
    re.compile(
        r"\b(?:прочи\w+\s+)?поручени\w*\s+(?:руководств\w*|руководител\w*|главного\s+аудитора"
        r"|президента|председател\w*)"
    ),
    re.compile(r"\b(?:согласно|в\s+соответствии\s+с)\s+(?:действующ\w+\s+)?законодательств\w*"),
    re.compile(r"\bв\s+пределах\s+(?:своей\s+)?компетенци\w*"),
)
# Слова, которые без предметной части не делают функцию содержательной.
_GENERIC_STEMS = frozenset(
    tokenize(
        "осуществляет осуществлять осуществление выполняет выполнять выполнение исполняет "
        "исполнение прочие прочих иные иных другие других функции обязанности задачи"
    )
)
MIN_CONTENT_TOKENS = 2


def strip_templates(text: str) -> str:
    """Текст без шаблонных оборотов (нормализованный)."""
    value = normalize_text(text)
    for rx in _TEMPLATE_RES:
        value = rx.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip()


def is_template(text: str) -> bool:
    """Шаблонная формулировка: после снятия шаблонных оборотов не остаётся предметной части."""
    content = [t for t in tokenize(strip_templates(text)) if t not in _GENERIC_STEMS]
    return len(content) < MIN_CONTENT_TOKENS


def _similarity(a: str, b: str) -> float:
    """Похожесть для отображения (0..1, Жаккар по токенам): ранжирует, но не решает."""
    if normalize_text(a) == normalize_text(b):
        return 1.0
    ta, tb = set(tokenize(a)), set(tokenize(b))
    if not ta or not tb:
        return 0.0
    return round(len(ta & tb) / len(ta | tb), 3)


def find_duplicate_candidates(
    functions: list[Function], k: int = TOP_K, llm: LLM | None = None
) -> list[tuple[Function, Function, float]]:
    """Пары функций РАЗНЫХ подразделений одной версии — кандидаты в дубли для S11.

    Внутри одного подразделения пары не строятся; шаблонные формулировки («иные функции»,
    «поручения руководства», «согласно законодательству», «в пределах компетенции») снимаются
    до поиска, а функция, у которой кроме них ничего нет, в поиск не идёт.
    """
    usable = [
        fn
        for fn in functions
        if fn.modality != "prohibition" and fn.unit_id is not None and not is_template(fn.text)
    ]
    by_version: dict[str, list[Function]] = {}
    for fn in usable:
        by_version.setdefault(fn.sources[0].version, []).append(fn)

    pairs: dict[tuple[str, str], tuple[Function, Function, float]] = {}
    for group in by_version.values():
        texts = [strip_templates(fn.text) for fn in group]
        vectors = _vectors(texts, llm)
        index = _Index(texts, [fn.signature for fn in group], vectors)
        for qi, fn in enumerate(group):

            def allowed(i: int, unit: str | None = fn.unit_id) -> bool:
                return group[i].unit_id != unit

            for i, _score, _reasons in index.rank(texts[qi], fn.signature, vectors[qi], k, allowed):
                other = group[i]
                first, second = (fn, other) if fn.id < other.id else (other, fn)
                key = (first.id, second.id)
                if key not in pairs:
                    pairs[key] = (first, second, _similarity(texts[qi], texts[i]))
    return sorted(pairs.values(), key=lambda p: (-p[2], p[0].id, p[1].id))
