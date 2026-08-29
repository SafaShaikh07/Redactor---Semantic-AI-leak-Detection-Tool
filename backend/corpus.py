import os
from pathlib import Path
from typing import Tuple, List
from sentence_transformers import SentenceTransformer, util

# Resolve corpus directory relative to this file
CORPUS_DIR = Path(__file__).parent.parent / "corpus"

print(f"Loading SentenceTransformer model 'all-MiniLM-L6-v2'...")
model = SentenceTransformer("all-MiniLM-L6-v2")

doc_names: List[str] = []
doc_embeddings = []

def _load_and_embed_corpus():
    global doc_names, doc_embeddings
    
    if not CORPUS_DIR.exists():
        print(f"Warning: Corpus directory {CORPUS_DIR} does not exist.")
        return

    doc_files = list(CORPUS_DIR.glob("*.txt"))
    if not doc_files:
        print(f"Warning: No .txt files found in {CORPUS_DIR}.")
        return

    doc_texts = []
    for file_path in doc_files:
        try:
            content = file_path.read_text(encoding="utf-8")
            doc_names.append(file_path.name)
            doc_texts.append(content)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    if doc_texts:
        print(f"Embedding {len(doc_texts)} documents from {CORPUS_DIR}...")
        doc_embeddings = model.encode(doc_texts, convert_to_tensor=True)
        print("Corpus loaded and embedded successfully.")

# Load corpus at module import / startup
_load_and_embed_corpus()


def most_similar(text: str) -> Tuple[str, float]:
    """
    Embeds incoming text and returns the closest corpus doc name + cosine similarity score.
    Prints similarity scores to console for debugging.
    """
    if not doc_names or len(doc_embeddings) == 0:
        print("Debug: Corpus is empty or not loaded.")
        return ("", 0.0)

    query_embedding = model.encode(text, convert_to_tensor=True)
    cosine_scores = util.cos_sim(query_embedding, doc_embeddings)[0]

    best_score = -1.0
    best_doc = ""

    print(f"\n--- Debug: Similarity Scores for query: {text!r} ---")
    for name, score_tensor in zip(doc_names, cosine_scores):
        score = float(score_tensor)
        print(f"  {name}: {score:.4f}")
        if score > best_score:
            best_score = score
            best_doc = name

    print(f"Top match: {best_doc} with score {best_score:.4f}\n")
    return (best_doc, best_score)
