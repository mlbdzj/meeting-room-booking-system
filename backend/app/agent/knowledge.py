"""知识库检索：面向中文短问题的字符级相似度匹配，无需额外分词依赖。"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Knowledge

PUNCTUATION_PATTERN = re.compile(r"[\s，。？！、,.?!:：;；~～\-_/\\()（）\[\]【】\"'“”‘’]+")


def normalize(text: str | None) -> str:
    return PUNCTUATION_PATTERN.sub("", (text or "")).lower()


def _grams(text: str) -> set[str]:
    if len(text) < 2:
        return {text} if text else set()
    return {text[index : index + 2] for index in range(len(text) - 1)}


def _keyword_list(entry: Knowledge) -> list[str]:
    return [normalize(item) for item in re.split(r"[,，、;；\s]+", entry.keywords or "") if normalize(item)]


def score_entry(query: str, entry: Knowledge) -> float:
    normalized_query = normalize(query)
    if not normalized_query:
        return 0.0

    question = normalize(entry.question)
    query_grams = _grams(normalized_query)
    question_grams = _grams(question)
    overlap = len(query_grams & question_grams) / max(1, len(query_grams))

    score = overlap * 2.0
    score += sum(1.4 for keyword in _keyword_list(entry) if keyword and keyword in normalized_query)
    if question and question in normalized_query:
        score += 1.5
    if normalized_query in question:
        score += 0.8
    if entry.category and normalize(entry.category) in normalized_query:
        score += 0.6
    return score


def similarity(query: str, entry: Knowledge) -> float:
    """问题与知识条目问题的字符重合度，用于判断是否为同一问题。"""
    normalized_query = normalize(query)
    question = normalize(entry.question)
    if not normalized_query or not question:
        return 0.0
    query_grams = _grams(normalized_query)
    question_grams = _grams(question)
    return len(query_grams & question_grams) / max(1, len(query_grams))


def search_knowledge(db: Session, query: str, limit: int = 3, min_score: float = 0.45) -> list[dict]:
    entries = db.scalars(select(Knowledge).where(Knowledge.status == 1)).all()
    scored = [(score_entry(query, entry), entry) for entry in entries]
    scored = [item for item in scored if item[0] >= min_score]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "id": entry.id,
            "category": entry.category,
            "question": entry.question,
            "answer": entry.answer,
            "score": round(score, 2),
            "similarity": round(similarity(query, entry), 2),
        }
        for score, entry in scored[:limit]
    ]


def faq_questions(db: Session, limit: int = 6) -> list[str]:
    entries = db.scalars(
        select(Knowledge).where(Knowledge.status == 1).order_by(Knowledge.id.asc()).limit(limit)
    ).all()
    return [entry.question for entry in entries]
