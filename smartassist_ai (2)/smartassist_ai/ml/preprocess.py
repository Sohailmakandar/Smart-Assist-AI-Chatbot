"""
Text Preprocessing Pipeline
----------------------------
Cleans, normalizes and tokenizes raw customer queries before they are
handed to the TF-IDF vectorizer. Kept dependency-free (no nltk/spacy
downloads) so the whole system runs offline out of the box.
"""

import re

# A small set of contractions so "can't" / "won't" style phrasing
# doesn't get mangled by the tokenizer.
CONTRACTIONS = {
    "can't": "cannot", "won't": "will not", "don't": "do not",
    "doesn't": "does not", "didn't": "did not", "isn't": "is not",
    "aren't": "are not", "wasn't": "was not", "weren't": "were not",
    "haven't": "have not", "hasn't": "has not", "hadn't": "had not",
    "i'm": "i am", "i've": "i have", "i'll": "i will", "i'd": "i would",
    "it's": "it is", "that's": "that is", "there's": "there is",
    "what's": "what is", "let's": "let us", "you're": "you are",
    "you've": "you have", "we're": "we are", "they're": "they are",
}

STOPWORDS = {
    "a", "an", "the", "is", "am", "are", "was", "were", "be", "been",
    "being", "to", "of", "in", "on", "at", "for", "with", "about",
    "as", "by", "and", "or", "but", "if", "so", "this", "that",
    "these", "those", "it", "its", "i", "you", "he", "she", "we",
    "they", "my", "your", "me", "do", "does", "did", "have", "has",
    "had", "will", "would", "can", "could", "should",
}

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")
_MULTISPACE_RE = re.compile(r"\s+")


def expand_contractions(text: str) -> str:
    for contraction, expansion in CONTRACTIONS.items():
        text = re.sub(rf"\b{re.escape(contraction)}\b", expansion, text)
    return text


def clean_text(text: str) -> str:
    """Lower-case, strip URLs/emails/punctuation, collapse whitespace."""
    text = text.lower().strip()
    text = _URL_RE.sub(" ", text)
    text = _EMAIL_RE.sub(" ", text)
    text = expand_contractions(text)
    text = _NON_ALNUM_RE.sub(" ", text)
    text = _MULTISPACE_RE.sub(" ", text).strip()
    return text


def tokenize(text: str, remove_stopwords: bool = True):
    cleaned = clean_text(text)
    tokens = cleaned.split()
    if remove_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]
    return tokens


def preprocess_for_vectorizer(text: str) -> str:
    """Return a cleaned string ready to hand to TfidfVectorizer.

    We keep stopwords in for the vectorizer (TF-IDF's own
    ``stop_words='english'`` handles that step) so this mainly
    normalizes casing, punctuation and contractions.
    """
    return clean_text(text)
