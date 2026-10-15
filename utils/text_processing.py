"""Text processing and query generation utilities."""

import re
from typing import List, Set, Tuple, Optional

COMMON_ACADEMIC_STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "cannot", "could", "did", "do", "does", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "has", "have", "having", "he", "her", "here",
    "hers", "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is", "isn't", "it",
    "its", "itself", "let's", "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "off",
    "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who",
    "whom", "why", "with", "would", "you", "your", "yours", "yourself", "yourselves",
    # Academic filler words
    "study", "paper", "research", "results", "analysis", "demonstrate", "proposed", "method", "presents",
    "using", "based", "novel", "investigates", "discusses", "concludes", "found", "provide", "approach"
}


def clean_text(text: str) -> str:
    """Removes weird characters, normalizes whitespace."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_key_phrases(text: str, max_phrases: int = 8) -> List[str]:
    """Heuristic extraction of key technical n-grams and scientific terms."""
    if not text:
        return []

    # Clean text to alphanumeric and spaces
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", " ", text.lower())
    words = [w for w in cleaned.split() if len(w) > 2 and w not in COMMON_ACADEMIC_STOPWORDS]

    if not words:
        return []

    # Count frequencies of single words and bigrams
    freq: dict = {}
    for i in range(len(words)):
        w1 = words[i]
        freq[w1] = freq.get(w1, 0) + 1
        if i < len(words) - 1:
            w2 = words[i + 1]
            if w1 not in COMMON_ACADEMIC_STOPWORDS and w2 not in COMMON_ACADEMIC_STOPWORDS:
                bigram = f"{w1} {w2}"
                freq[bigram] = freq.get(bigram, 0) + 2  # Boost bigrams

    sorted_phrases = sorted(freq.items(), key=lambda item: item[1], reverse=True)
    return [p[0] for p in sorted_phrases[:max_phrases]]


def generate_search_query_variations(
    title: str,
    keywords: List[str],
    domain: str,
    key_concepts: Optional[List[str]] = None
) -> List[str]:
    """Generates targeted, differentiated scholarly search queries."""
    queries: List[str] = []

    # Clean title
    title_clean = clean_text(title)
    if title_clean:
        queries.append(title_clean)

    # Keywords combo
    if keywords:
        clean_kw = [k.strip() for k in keywords if len(k.strip()) > 2]
        if clean_kw:
            queries.append(" ".join(clean_kw[:4]))

    # Concepts + Domain
    if key_concepts and domain and domain != "General Science":
        concept_str = " ".join(key_concepts[:3])
        queries.append(f"{domain} {concept_str}")
    elif key_concepts:
        queries.append(" ".join(key_concepts[:3]))

    # Domain + Title Key N-grams
    title_phrases = extract_key_phrases(title, max_phrases=3)
    if title_phrases:
        if domain and domain != "General Science":
            queries.append(f"{domain} {' '.join(title_phrases)}")
        else:
            queries.append(" ".join(title_phrases))

    # Deduplicate while preserving order
    seen = set()
    final_queries = []
    for q in queries:
        norm = " ".join(q.lower().split())
        if norm and norm not in seen:
            seen.add(norm)
            final_queries.append(q)

    return final_queries


def calculate_jaccard_overlap(text1: str, text2: str) -> float:
    """Calculates word-level Jaccard similarity after removing stopwords."""
    words1 = {w for w in re.sub(r"[^a-zA-Z0-9\s]", " ", text1.lower()).split() if len(w) > 2 and w not in COMMON_ACADEMIC_STOPWORDS}
    words2 = {w for w in re.sub(r"[^a-zA-Z0-9\s]", " ", text2.lower()).split() if len(w) > 2 and w not in COMMON_ACADEMIC_STOPWORDS}

    if not words1 or not words2:
        return 0.0

    intersection = words1.intersection(words2)
    union = words1.union(words2)
    return len(intersection) / len(union)
