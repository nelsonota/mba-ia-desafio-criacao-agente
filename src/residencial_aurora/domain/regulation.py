"""Recuperação lexical limitada a artigos relevantes do regulamento."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
import unicodedata

from residencial_aurora.config import PROJECT_ROOT

CHAPTER_RE = re.compile(r"(?m)^##\s+(Capítulo\s+[IVXLCDM]+:.*)$", re.IGNORECASE)
ARTICLE_RE = re.compile(r"(?m)^\*\*Art\.\s*(\d+)\.\*\*")
TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
STOP_WORDS = {
    "a", "ao", "aos", "as", "com", "da", "das", "de", "do", "dos", "e", "em",
    "entre", "essa", "esse", "esta", "este", "horas", "me", "na", "nas", "no", "nos",
    "o", "os", "para", "por", "qual", "que", "se", "sobre", "um", "uma", "usar",
    "uso", "é", "às", "até", "quando", "qual", "qualquer",
}


@dataclass(frozen=True)
class RegulationArticle:
    number: str
    chapter: str
    text: str


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _tokens(text: str) -> set[str]:
    normalized = _normalize(text)
    return {token for token in TOKEN_RE.findall(normalized) if token not in STOP_WORDS and len(token) > 1}


@lru_cache(maxsize=1)
def load_articles() -> tuple[RegulationArticle, ...]:
    """Carrega e fragmenta o arquivo original uma vez por processo."""
    source = (PROJECT_ROOT / "dados" / "regulamento.md").read_text(encoding="utf-8")
    chapters = list(CHAPTER_RE.finditer(source))
    articles: list[RegulationArticle] = []
    for chapter_index, chapter_match in enumerate(chapters):
        chapter_end = chapters[chapter_index + 1].start() if chapter_index + 1 < len(chapters) else len(source)
        chapter_text = source[chapter_match.end():chapter_end]
        matches = list(ARTICLE_RE.finditer(chapter_text))
        for index, match in enumerate(matches):
            article_end = matches[index + 1].start() if index + 1 < len(matches) else len(chapter_text)
            article_text = chapter_text[match.start():article_end].strip()
            articles.append(
                RegulationArticle(
                    number=match.group(1),
                    chapter=chapter_match.group(1).strip(),
                    text=article_text[:1400],
                )
            )
    return tuple(articles)


def search_regulation(question: str, limit: int = 2) -> dict[str, object]:
    """Retorna no máximo dois artigos curtos; nunca retorna o documento ou capítulo inteiro."""
    query_tokens = _tokens(question)
    if not query_tokens:
        return {"consulta": question, "trechos": []}

    hour_query = bool(query_tokens & {"horario", "fechamento", "fecha", "abertura", "abre", "funciona"})
    weekend_query = bool(query_tokens & {"domingo", "domingos", "feriado", "feriados"})
    ranked: list[tuple[int, RegulationArticle]] = []
    for article in load_articles():
        article_tokens = _tokens(article.text)
        chapter_tokens = _tokens(article.chapter)
        score = len(query_tokens & article_tokens) + 2 * len(query_tokens & chapter_tokens)
        if hour_query and re.search(r"\b\d{1,2}h(?:\d{2})?\b", _normalize(article.text)):
            score += 3
        if weekend_query and ("domingo" in _normalize(article.text) or "feriado" in _normalize(article.text)):
            score += 1
        if score:
            ranked.append((score, article))

    ranked.sort(key=lambda item: (-item[0], int(item[1].number)))
    if not ranked:
        return {"consulta": question, "trechos": []}

    best_score = ranked[0][0]
    selected = [item for item in ranked if item[0] >= max(2, best_score - 1)][: max(1, min(limit, 2))]
    snippets = [
        {
            "artigo": item.number,
            "capitulo": item.chapter,
            "trecho": item.text,
        }
        for _, item in selected
    ]
    return {"consulta": question, "trechos": snippets}
