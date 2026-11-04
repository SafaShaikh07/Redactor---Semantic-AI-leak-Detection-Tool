import os
import re
import threading
from pathlib import Path
from typing import List, NamedTuple, Tuple
from sentence_transformers import SentenceTransformer

DEFAULT_SEMANTIC_THRESHOLD = 0.60
raw_threshold = os.getenv("REDACTOR_SEMANTIC_THRESHOLD", str(DEFAULT_SEMANTIC_THRESHOLD))
try:
    SEMANTIC_THRESHOLD = float(raw_threshold)
except ValueError as exc:
    raise ValueError("REDACTOR_SEMANTIC_THRESHOLD must be a number between 0 and 1") from exc
if not 0.0 <= SEMANTIC_THRESHOLD <= 1.0:
    raise ValueError("REDACTOR_SEMANTIC_THRESHOLD must be a number between 0 and 1")

CORPUS_DIR = Path(
    os.getenv("REDACTOR_CORPUS_DIR", str(Path(__file__).parent.parent / "corpus"))
).expanduser().resolve()

print(f"Loading SentenceTransformer model 'all-MiniLM-L6-v2'...")
model = SentenceTransformer("all-MiniLM-L6-v2")
_model_lock = threading.Lock()

doc_names: List[str] = []
doc_embeddings = None


class SemanticResult(NamedTuple):
    doc_name: str
    score: float
    start: int
    end: int


def _split_sentences(text: str) -> List[str]:
    normalized_text = " ".join(text.split())
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", normalized_text)
        if sentence.strip()
    ]


def _sentence_spans(text: str) -> List[Tuple[int, int, str]]:
    spans = []
    start = 0
    for boundary in re.finditer(r"(?<=[.!?])\s+(?=[A-Z])", text):
        end = boundary.start()
        while start < end and text[start].isspace():
            start += 1
        if start < end:
            spans.append((start, end, text[start:end]))
        start = boundary.end()
    end = len(text)
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if start < end:
        spans.append((start, end, text[start:end]))
    return spans

def _load_and_embed_corpus():
    global doc_names, doc_embeddings

    doc_names.clear()
    doc_embeddings = None
    if not CORPUS_DIR.exists():
        print(f"Warning: Corpus directory {CORPUS_DIR} does not exist.")
        return

    doc_files = list(CORPUS_DIR.glob("*.txt"))
    if not doc_files:
        print(f"Warning: No .txt files found in {CORPUS_DIR}.")
        return

    reference_chunks = []
    for file_path in doc_files:
        try:
            chunks = _split_sentences(file_path.read_text(encoding="utf-8"))
            doc_names.extend([file_path.name] * len(chunks))
            reference_chunks.extend(chunks)
        except Exception as exc:
            print(f"Error reading {file_path}: {exc}")

    if reference_chunks:
        print(f"Embedding {len(reference_chunks)} reference sentences from {CORPUS_DIR}...")
        doc_embeddings = model.encode(
            reference_chunks,
            convert_to_tensor=True,
            normalize_embeddings=True
        )
        print("Corpus loaded and embedded successfully.")

# Load corpus at module import / startup
_load_and_embed_corpus()


def most_similar(text: str) -> Tuple[str, float]:
    result = analyze_semantic(text)
    return result.doc_name, result.score


def analyze_semantic(text: str) -> SemanticResult:
    if not text.strip() or not doc_names or doc_embeddings is None:
        return SemanticResult("", 0.0, 0, len(text))

    prompt_spans = _sentence_spans(text)
    candidates = [(0, len(text), text.strip())] if len(prompt_spans) > 1 else []
    candidates.extend(prompt_spans)
    if not candidates:
        return SemanticResult("", 0.0, 0, len(text))

    with _model_lock:
        query_embeddings = model.encode(
            [candidate[2] for candidate in candidates],
            convert_to_tensor=True,
            normalize_embeddings=True
        )
    scores = query_embeddings @ doc_embeddings.T
    best_scores, best_reference_indices = scores.max(dim=1)

    sentence_offset = 1 if len(prompt_spans) > 1 else 0
    qualifying_indices = [
        index for index in range(sentence_offset, len(candidates))
        if float(best_scores[index]) >= SEMANTIC_THRESHOLD
    ]
    if qualifying_indices:
        selected_index = max(qualifying_indices, key=lambda index: float(best_scores[index]))
    else:
        selected_index = int(best_scores.argmax())

    reference_index = int(best_reference_indices[selected_index])
    start, end, _ = candidates[selected_index]
    return SemanticResult(
        doc_names[reference_index],
        float(best_scores[selected_index]),
        start,
        end
    )
