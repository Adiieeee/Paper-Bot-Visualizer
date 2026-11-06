# Baseline Project: GraphRAG Academic Paper Explorer

Dokumen ini berisi rangkuman komprehensif mengenai arsitektur, alur logika, dan batasan dari proyek *GraphRAG (tanpa Vector DB)* saat ini. Dokumen ini dirancang sebagai landasan (baseline) dan referensi bagi Anda untuk membangun sistem GraphRAG generasi berikutnya yang lebih mutakhir (menggunakan Vector Database, Embeddings, dan Hybrid Search).

---

## 1. Konsep Dasar & Tujuan
Proyek ini bertujuan untuk membangun asisten AI akademik yang mampu menjawab pertanyaan berdasarkan *Knowledge Graph* (Graf Pengetahuan) yang dibangun dari sekumpulan dokumen PDF (jurnal ilmiah). Sistem ini berfokus pada **struktur relasional eksplisit** antar entitas (seperti Metode, Dataset, Metrik, Temuan), menghindari halusinasi yang sering terjadi pada sistem RAG tradisional.

---

## 2. Arsitektur Data & Ontologi
Sistem ini memodelkan pengetahuan akademik ke dalam graf terarah/tidak terarah dengan skema berikut:
*   **Tipe Node (Entitas):** `Paper`, `Author`, `Institution`, `Method`, `Dataset`, `Metric`, `Finding`, `Limitation`.
*   **Tipe Edge (Relasi):** `uses_method`, `uses_dataset`, `uses_metric`, `has_limitation`, `compares`, `finds`, `proposes_method`, `criticizes`, `builds_on`, `written_by`, `affiliated_with`, `mentioned_in`.

---

## 3. Alur Pembangunan Graf (Ingestion Pipeline)

Proses mengubah teks PDF mentah menjadi *Knowledge Graph* dilakukan melalui 4 tahap utama (`main.py`):

### A. Parsing & Chunking (`app/extractor.py` & `app/chunker.py`)
1.  Sistem membaca file PDF menggunakan `PyMuPDF` (fitz).
2.  Teks panjang dipotong menjadi *chunk* (sekitar 1000-1500 kata).
3.  Hal ini dilakukan karena LLM memiliki batas *context window*, sehingga ekstraksi informasi harus dilakukan sepotong demi sepotong.

### B. LLM Information Extraction (`app/extractor.py`)
1.  Setiap *chunk* dikirim ke LLM (Google Gemini) dengan *prompt* khusus.
2.  LLM diinstruksikan untuk mengenali entitas (Named Entity Recognition) dan mengekstrak relasi antar entitas tersebut.
3.  Hasilnya dikembalikan dalam format JSON terstruktur murni dan di-*cache* (disimpan sementara) di `output/extractions/` untuk menghemat kuota API di masa mendatang.

### C. Entity Normalization & Linking (`app/graph_builder.py` & `app/entity_resolver.py`)
Tahap paling menantang. LLM sering mengekstrak entitas yang sama dengan ejaan berbeda (misal: "DenseNet" vs "Dense Convolutional Network").
1.  **Normalisasi Kasar:** Sistem melakukan konversi `.lower().strip()` untuk otomatis menggabungkan variasi *casing* (misal: "ImageNet" dan "imagenet").
2.  **LLM Entity Linking:** Daftar entitas baru dikirim kembali ke LLM secara *batch* (per 20 item). LLM membandingkan entitas baru ini dengan "Master List" entitas yang sudah diketahui. Jika dianggap bersinonim, LLM akan memetakannya (membuat kamus alias).
3.  **Proteksi Semantik (Prompt Engineering):** *Prompt* dilengkapi instruksi ketat (seperti mencegah hipernim dan mempertahankan angka versi) untuk menghindari *over-merging* (misal: mencegah penggabungan "Top-1 Error" dengan "Top-5 Error").
4.  **Cycle Detection:** Logika `while` loop yang memetakan entitas dilengkapi dengan pendeteksi siklus (himpunan `visited`) untuk mencegah *infinite loop* jika LLM menghasilkan pemetaan melingkar (A -> B -> A).

### D. Graph Construction (`app/graph_builder.py`)
1.  Menggunakan *library* `NetworkX` untuk membangun topologi Node dan Edge berdasarkan kamus deduplikasi di tahap sebelumnya.
2.  Node yang tidak terhubung ke graf utama (*orphan nodes*) secara paksa dihubungkan ke entitas `Paper` asalnya dengan relasi `mentioned_in` agar graf tidak terpecah belah.
3.  Graf diekspor dalam format `graph.graphml`.

---

## 4. Alur Interaksi & GraphRAG Chatbot (`app/chatbot.py`)

Saat pengguna mengetik pertanyaan di antarmuka Web UI, inilah yang terjadi di balik layar:

1.  **Query Resolver (`app/query_resolver.py`):**
    *   Pertanyaan dikirim ke LLM untuk diekstrak entitas kuncinya. *Prompt* secara spesifik melarang LLM menyertakan kata kategori seperti "Paper" atau "Dataset" pada hasil ekstraksi.
    *   Entitas yang terekstrak difilter secara mekanis (menghapus *stop words*), kemudian dicocokkan dengan *node* di graf.
    *   Pencocokan berlapis ganda: (a) *Exact match* ke *alias dictionary*, (b) *Exact match* ke *node list*, (c) *Fuzzy match* menggunakan `SequenceMatcher` (threshold > 0.70).
2.  **Graph Traversal (`app/graph_traversal.py`):**
    *   Dari *node* hasil pencocokan (*entry point*), sistem menggunakan `NetworkX` untuk menarik semua *neighbor* (tetangga) dengan jarak 1-hop beserta tipe relasinya.
    *   *Proteksi:* Node bertipe `Paper` tidak dilewati lebih jauh untuk mencegah ledakan konteks (konteks yang melompat ke topik lain yang tidak relevan).
3.  **Context Serialization:**
    *   Sub-graf 1-hop tersebut diubah menjadi teks naratif yang mudah dibaca oleh LLM (misal: *"DenseNet memiliki kelemahan berupa Overfitting"*).
4.  **LLM Generation (`app/chatbot.py`):**
    *   Teks naratif disuntikkan sebagai `<KONTEKS GRAPH>` ke dalam *prompt* bersama dengan pertanyaan asli dari pengguna.
    *   LLM (dengan Temperature = 0) diinstruksikan dengan ketat untuk **hanya** menjawab berdasarkan konteks tersebut, memberikan hasil yang ter-grounding penuh (bebas halusinasi).

---

## 5. Batasan Sistem Saat Ini & Alasan Beralih ke Vector DB

Meskipun sistem ini berhasil memperlihatkan topologi pengetahuan secara visual, sistem ini memiliki titik lemah (*bottleneck*) arsitektural yang membuatnya sulit di-skala ke ratusan PDF:

1.  **Entity Linking Sangat Mahal & Lambat:**
    Saat ini, deduplikasi entitas mengandalkan LLM API (`generateContent`). Untuk setiap entitas baru, kita membakar token API. Ini lambat, mahal, rentan terhadap format JSON yang cacat, dan terkadang LLM bandel (over-merging).
2.  **Query Resolving Rentan Gagal:**
    Pencarian *entry point* mengandalkan `SequenceMatcher` (Fuzzy Match tekstual). Jika pengguna mencari "Image Classification Challenge", sistem mungkin gagal mencocokkannya dengan "ILSVRC-2012" karena secara huruf tidak mirip sama sekali, padahal maknanya sama.
3.  **Tidak Ada Semantic Search (Pencarian Makna):**
    Sistem saat ini bergantung 100% pada *exact/fuzzy string matching* dari struktur *node*. Jika pertanyaan pengguna tidak memuat *Named Entity* yang jelas, sistem akan buta.

---

## 6. Desain Proyek Selanjutnya (True GraphRAG + Vector DB)

Untuk proyek Anda berikutnya, pertimbangkan perombakan arsitektur berikut untuk mengatasi kelemahan di atas:

### A. Gantikan LLM Entity Linking dengan Vector Embeddings
Daripada meminta LLM membandingkan "DenseNet" dan "Dense Convolutional Network", lakukan langkah ini:
1.  Ubah semua nama *node* menjadi *Vector Embedding* (misal menggunakan OpenAI `text-embedding-3-small` atau model HuggingFace `all-MiniLM-L6-v2`).
2.  Simpan ke dalam Vector Database (seperti **Milvus, Pinecone, Weaviate, atau Qdrant**).
3.  Lakukan pencarian Cosine Similarity > 0.85 untuk menggabungkan entitas yang mirip secara makna. Ini jauh lebih cepat, stabil, dan murah dibanding memanggil LLM *text-generation*.

### B. Hybrid Search pada Query Resolver
Saat *user* bertanya, jalankan **Hybrid Search**:
1.  Ubah pertanyaan *user* menjadi vektor, temukan *node* terdekat di Vector DB (Semantic Match).
2.  Kombinasikan dengan Keyword/Entity Extraction (Lexical Match).
3.  Dari titik-titik temu tersebut, lakukan *Graph Traversal* (bisa ditingkatkan menjadi 2-hop atau menggunakan teknik *Community Summary* ala Microsoft GraphRAG).

### C. Chunk-to-Node Linking
Alih-alih membuang teks asli, simpan *chunk* teks mentah (berisi kalimat-kalimat utuh dari PDF) ke dalam Vector DB, dan jadikan *chunk* tersebut sebagai properti (metadata) di dalam *node* graf. 
Jika *traversal* graf tidak memberikan informasi yang cukup detail, sistem dapat menarik vektor teks asli dari *chunk* yang bersangkutan.
