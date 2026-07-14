"""
config.py — Konfigurasi global untuk Graph RAG Paper Explorer.
Semua konstanta, schema, dan parameter ada di sini.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Gunakan path absolut relatif ke lokasi config.py ini,
# supaya .env selalu ditemukan tidak peduli dari mana main.py dipanggil.
_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)

# ─── Gemini API ───────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Model utama: gemini-2.0-flash-lite — lebih hemat quota di free tier
# Ganti ke "gemini-2.0-flash" untuk kualitas lebih tinggi jika quota cukup
# Ganti ke "gemini-1.5-flash" sebagai fallback jika flash-lite juga habis
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

# Rate limiting — lebih konservatif dari spesifikasi (3 detik vs 1 detik)
# untuk menghindari 15 RPM limit pada Gemini free tier
API_DELAY_SECONDS = 3
API_MAX_RETRIES = 3
API_RETRY_DELAY_SECONDS = 10

# ─── Chunking ─────────────────────────────────────────────────
CHUNK_SIZE = 3500
CHUNK_OVERLAP = 500

# ─── Section Filter ───────────────────────────────────────────
# Pattern regex lebih robust daripada plain keyword matching.
# Handle variasi: "5. References", "REFERENCES", "5 References", dll.
SECTION_SKIP_PATTERNS = [
    r"^\s*\d*[.\s]*references?\s*$",
    r"^\s*\d*[.\s]*bibliography\s*$",
    r"^\s*\d*[.\s]*appendix\s*[a-z]?\s*$",
    r"^\s*\d*[.\s]*appendices\s*$",
    r"^\s*\d*[.\s]*acknowledgm?ents?\s*$",
    r"^\s*\d*[.\s]*notes?\s*$",
    r"^\s*\d*[.\s]*supplementary\s*(material)?\s*$",
]

# ─── Node Colors (untuk Pyvis) ────────────────────────────────
NODE_COLORS = {
    "Paper":       "#4A90D9",
    "Author":      "#E74C3C",
    "Institution": "#34495E",
    "Method":      "#2ECC71",
    "Dataset":     "#F39C12",
    "Metric":      "#E67E22",
    "Finding":     "#9B59B6",
    "Limitation":  "#95A5A6",
}

# ─── Schema ───────────────────────────────────────────────────
VALID_ENTITY_TYPES = [
    "Paper", "Author", "Institution", "Method",
    "Dataset", "Metric", "Finding", "Limitation",
]

VALID_RELATIONSHIP_TYPES = [
    "written_by", "affiliated_with", "uses_method", "proposes_method",
    "uses_dataset", "uses_metric", "finds", "has_limitation",
    "criticizes", "builds_on", "compares", "same_author",
]

# ─── Deduplication ────────────────────────────────────────────
# Threshold 0.85 sedikit lebih tinggi dari spec (0.8) untuk kurangi
# false positives antar metode yang berbeda tapi namanya mirip.
ENTITY_SIMILARITY_THRESHOLD = 0.85

# Kamus akronim umum ML/AI — safety net jika LLM tetap return akronim.
# Key: lowercase akronim, Value: nama lengkap yang dipakai sebagai canonical.
COMMON_ACRONYMS: dict[str, str] = {
    "rag":   "Retrieval-Augmented Generation",
    "llm":   "Large Language Model",
    "llms":  "Large Language Models",
    "nlp":   "Natural Language Processing",
    "bert":  "Bidirectional Encoder Representations from Transformers",
    "gpt":   "Generative Pre-trained Transformer",
    "gpt-4": "GPT-4",
    "gpt-3": "GPT-3",
    "lora":  "Low-Rank Adaptation",
    "rlhf":  "Reinforcement Learning from Human Feedback",
    "qa":    "Question Answering",
    "kg":    "Knowledge Graph",
    "nn":    "Neural Network",
    "dl":    "Deep Learning",
    "ml":    "Machine Learning",
    "ai":    "Artificial Intelligence",
    "gcn":   "Graph Convolutional Network",
    "gnn":   "Graph Neural Network",
    "cnn":   "Convolutional Neural Network",
    "rnn":   "Recurrent Neural Network",
    "lstm":  "Long Short-Term Memory",
    "sft":   "Supervised Fine-Tuning",
    "peft":  "Parameter-Efficient Fine-Tuning",
    "vllm":  "vLLM",
    "faiss": "Facebook AI Similarity Search",
    "bm25":  "BM25 Retrieval",
    "tfidf": "TF-IDF",
    "dpr":   "Dense Passage Retrieval",
    "hnsw":  "Hierarchical Navigable Small World",
    "ann":   "Approximate Nearest Neighbor",
    "knn":   "K-Nearest Neighbor",
    "svm":   "Support Vector Machine",
    "rf":    "Random Forest",
    "xgb":   "XGBoost",
    "t5":    "T5 (Text-to-Text Transfer Transformer)",
    "bart":  "BART (Bidirectional and Auto-Regressive Transformers)",
    "moe":   "Mixture of Experts",
    "rag-token": "RAG-Token",
    "rag-sequence": "RAG-Sequence",
    "hyde":  "Hypothetical Document Embeddings",
    "flare": "Forward-Looking Active Retrieval",
    "self-rag": "Self-RAG",
    "crag":  "Corrective RAG",
    "graph-rag": "Graph RAG",
}

# Terms yang TIDAK boleh menjadi node (terlalu generik)
GENERIC_ENTITY_BLOCKLIST = {
    "the model", "the approach", "the method", "the dataset",
    "the system", "the algorithm", "this model", "our model",
    "the proposed method", "our approach", "the proposed approach",
    "the framework", "our framework", "this framework",
    "the technique", "the network", "the architecture",
    "a model", "a method", "an approach",
    "model", "method", "approach", "technique",
}

# ─── Paths ────────────────────────────────────────────────────
PAPERS_DIR       = "papers"
OUTPUT_DIR       = "output"
EXTRACTIONS_DIR  = "output/extractions"
GRAPH_HTML_PATH  = "output/graph.html"
GRAPH_GRAPHML_PATH = "output/graph.graphml"
LOG_FILE_PATH    = "output/extraction_log.txt"
