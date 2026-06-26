from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_DOCS_DIR = Path(__file__).resolve().parents[2] / "data" / "weather_docs"

DOMAIN_TERMS = [
    "体感温度",
    "湿度",
    "闷热",
    "降水概率",
    "阵雨",
    "雷暴",
    "阵风",
    "大风",
    "紫外线",
    "高温",
    "中暑",
    "霜冻",
    "农业",
    "喷药",
    "通勤",
    "骑行",
    "跑步",
    "露营",
    "户外",
    "预报",
    "不确定性",
]


@dataclass
class DocumentChunk:
    id: str
    title: str
    text: str
    source: str


@dataclass
class SearchResult:
    chunk: DocumentChunk
    score: float


class LocalVectorStore:
    def __init__(self, chunks: list[DocumentChunk], dimensions: int = 256) -> None:
        self.chunks = chunks
        self.dimensions = dimensions
        self.vectors = [embed_text(chunk.title + "\n" + chunk.text, dimensions) for chunk in chunks]

    @classmethod
    def from_directory(cls, docs_dir: Path | str = DEFAULT_DOCS_DIR) -> "LocalVectorStore":
        return cls(load_documents(Path(docs_dir)))

    def search(self, query: str, top_k: int = 4) -> list[SearchResult]:
        query_vector = embed_text(query, self.dimensions)
        scored = [
            SearchResult(chunk=chunk, score=cosine_similarity(query_vector, vector))
            for chunk, vector in zip(self.chunks, self.vectors)
        ]
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]


def load_documents(docs_dir: Path) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8").strip()
        title_match = re.search(r"^#\s+(.+)$", content, flags=re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem
        body = re.sub(r"^#\s+.+$", "", content, count=1, flags=re.MULTILINE).strip()
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
        if not paragraphs:
            paragraphs = [body]

        for index, paragraph in enumerate(group_paragraphs(paragraphs), start=1):
            chunks.append(
                DocumentChunk(
                    id=f"{path.stem}-{index}",
                    title=title,
                    text=paragraph,
                    source=path.name,
                )
            )
    return chunks


def group_paragraphs(paragraphs: list[str], max_chars: int = 520) -> Iterable[str]:
    buffer: list[str] = []
    size = 0
    for paragraph in paragraphs:
        if buffer and size + len(paragraph) > max_chars:
            yield "\n".join(buffer)
            buffer = []
            size = 0
        buffer.append(paragraph)
        size += len(paragraph)
    if buffer:
        yield "\n".join(buffer)


def tokenize(text: str) -> list[str]:
    normalized = text.lower()
    tokens = re.findall(r"[a-z0-9_\-]+", normalized)
    tokens.extend(re.findall(r"[\u4e00-\u9fff]{2,}", normalized))

    for term in DOMAIN_TERMS:
        if term in text:
            tokens.extend([term] * 3)

    chinese_sequences = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    for sequence in chinese_sequences:
        tokens.extend(sequence[index : index + 2] for index in range(max(len(sequence) - 1, 0)))
    return tokens


def embed_text(text: str, dimensions: int = 256) -> list[float]:
    vector = [0.0] * dimensions
    tokens = tokenize(text)
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1 if digest[4] % 2 == 0 else -1
        weight = 1.0 + min(len(token), 8) / 16
        vector[bucket] += sign * weight

    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [value / norm for value in vector]
    return vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))
