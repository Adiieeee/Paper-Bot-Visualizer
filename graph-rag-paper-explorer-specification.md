# Spesifikasi Proyek: Graph RAG Academic Paper Explorer (Versi Minimal)

## 1. Konteks & Tujuan

### 1.1 Apa Ini

Aplikasi yang menerima PDF paper akademik sebagai input, mengekstrak entitas dan relasi dari konten paper menggunakan LLM, membangun knowledge graph, dan memvisualisasikannya sebagai graph interaktif.

### 1.2 Tujuan

- **Mendemonstrasikan Graph RAG** — menunjukkan bagaimana graph dari dokumen memberikan insight yang tidak bisa didapat dari Vector RAG biasa
- **Versi minimal** — fokus pada pipeline ekstraksi dan visualisasi. Tidak ada chatbot, tidak ada detail panel, tidak ada deployment
- **Berjalan lokal** — semuanya di laptop, tanpa server, tanpa database, tanpa deployment
- **Budget $0**

### 1.3 Apa Bukan

- Bukan chatbot (chatbot akan ditambahkan di versi selanjutnya)
- Bukan pengganti Connected Papers atau Semantic Scholar
- Bukan tools produksi — ini learning project

### 1.4 Perbedaan dengan Vector RAG

Vector RAG mencari teks berdasarkan kemiripan makna. Graph RAG membangun jaringan entitas dan relasi, memungkinkan pertanyaan multi-hop dan pemahaman hubungan antar entitas. Versi ini fokus pada **pembuatan dan visualisasi graph** — query/chat akan ditambahkan nanti.

---

## 2. Arsitektur

### 2.1 Pipeline

```
PDF Paper (input user)
      │
      ▼
[1. PDF Parser] ── PyMuPDF ──→ teks mentah per paper
      │
      ▼
[2. Section Filter] ── hapus References & Appendix ──→ teks bersih
      │
      ▼
[3. Chunking] ── pecah jadi chunk ──→ ~2-3 chunk per paper
      │
      ▼
[4. Entity Extraction] ── Gemini Flash + schema ──→ JSON (entities + relationships)
      │
      ▼
[5. Merge & Deduplicate] ── gabungkan, resolusi duplikat ──→ clean graph data
      │
      ▼
[6. Graph Builder] ── NetworkX ──→ graph object
      │
      ▼
[7. Visualizer] ── Pyvis ──→ graph.html (file HTML interaktif)
      │
      ▼
[8. Export] ── GraphML ──→ graph.graphml (file persisten)
```

### 2.2 Penjelasan Setiap Tahap

#### Tahap 1: PDF Parser

- Menggunakan **PyMuPDF** (library `fitz`), BUKAN PyPDF2
- Alasan: PyMuPDF lebih baik handle layout dua kolom pada paper akademik
- Output: teks mentah per halaman, dengan metadata nomor halaman
- Opsi tambahan: kalau paper dari arXiv, bisa gunakan sumber LaTeX sebagai pengganti PDF untuk kualitas teks yang lebih baik (ini opsional, bukan wajib)

#### Tahap 2: Section Filter

Menghapus bagian yang tidak mengandung entitas bernilai:

**Bagian yang DIPROSES (pertahankan):**
- Abstract
- Introduction
- Methodology / Methods
- Experiments / Results (hanya bagian yang berisi temuan utama, bukan detail tabel angka)
- Discussion
- Conclusion

**Bagian yang DIHAPUS (lewati):**
- References / Bibliography (sitasi bisa di-parse dengan regex tanpa LLM, tapi untuk versi minimal ini tidak perlu)
- Appendix
- Acknowledgments
- Daftar isi
- Rumus matematika yang panjang (bukan teks naratif)

**Implementasi:**
- Cara paling sederhana: berdasarkan keyword heading. Jika menemukan baris yang hanya berisi "References" atau "Appendix", hentikan proses.
- Cara lebih baik: gunakan LLM untuk mengidentifikasi section boundaries. Tapi untuk versi minimal, pendekatan keyword sudah cukup.

#### Tahap 3: Chunking

- **Chunk size: 3000-4000 karakter** (lebih besar dari RAG biasa karena ekstraksi entitas butuh lebih konteks)
- **Chunk overlap: 500 karakter**
- Menggunakan `RecursiveCharacterTextSplitter` dari LangChain atau implementasi sederhana sendiri
- Tidak perlu terlalu presisi — beda dengan RAG, chunk di sini hanya untuk memastikan tidak melebihi context window LLM

**Estimasi:** Paper 20 halaman setelah filter ≈ 8.000-10.000 kata ≈ 2-3 chunk

#### Tahap 4: Entity Extraction

Ini adalah **tahap paling penting**. Setiap chunk dikirim ke Gemini Flash dengan prompt yang meminta ekstraksi entitas dan relasi dalam format JSON.

**Lihat Bagian 3 untuk detail schema dan prompt.**

#### Tahap 5: Merge & Deduplicate

Setelah semua chunk diekstrak, hasilnya perlu digabungkan:

1. **Gabungkan** semua JSON dari semua chunk semua paper
2. **Deduplicate entitas**: "RAG" dan "Retrieval Augmented Generation" dan "RAG (Retrieval-Augmented Generation)" seharusnya menjadi satu node
3. **Deduplicate relasi**: edge yang sama dari dua chunk berbeda tidak perlu diduplikasi

**Implementasi deduplikasi sederhana:**
- Normalisasi nama entitas: lowercase, strip whitespace, hapus tanda kurung
- Untuk nama yang terlalu generik ("the model", "this approach"), hapus — bukan entitas yang bermakna
- Gunakan **string similarity** (misalnya ratio dari difflib.SequenceMatcher) dengan threshold 0.8 untuk menggabungkan entitas yang mirip

#### Tahap 6: Graph Builder

- Menggunakan **NetworkX** (library Python)
- Setiap entitas menjadi **node** dengan atribut: `type`, `name`, `source_paper`, `source_page`
- Setiap relasi menjadi **edge** dengan atribut: `type` (jenis relasi), `source_paper`, `description`
- Graph disimpan di memori

#### Tahap 7: Visualizer

- Menggunakan **Pyvis** (`pyvis.network.Network`)
- Output: file `graph.html` yang bisa dibuka di browser
- Graph harus **interaktif**: drag node, zoom, hover untuk melihat info
- Node dikelompokkan berdasarkan tipe dengan **warna berbeda**

**Skema warna node:**
| Tipe Entitas | Warna |
|---|---|
| Paper | Biru (#4A90D9) |
| Author | Merah (#E74C3C) |
| Method | Hijau (#2ECC71) |
| Dataset | Oranye (#F39C12) |
| Finding | Ungu (#9B59B6) |
| Limitation | Abu-abu (#95A5A6) |
| Institution | Biru tua (#2C3E50) |

**Label edge:** tampilkan jenis relasi saat hover (jangan selalu tampilkan, agar graph tidak ramai)

**Layout:** gunakan force-directed layout (default Pyvis), yang secara otomatis menempatkan node yang terhubung dekat satu sama lain.

#### Tahap 8: Export

- Simpan graph dalam format **GraphML** (`graph.graphml`) menggunakan `nx.write_graphml()`
- GraphML bisa dibuka kembali tanpa menjalankan ulang ekstraksi
- Simpan juga JSON hasil ekstraksi mentah di folder `output/extractions/` untuk debugging

---

## 3. Schema Ekstraksi

### 3.1 Jenis Entitas (Node)

| Tipe | Deskripsi | Contoh |
|---|---|---|
| `Paper` | Paper akademik itu sendiri | "Improving RAG with Re-ranking" |
| `Author` | Penulis paper | "Chen, Wei" |
| `Institution` | Afiliasi penulis | "Stanford University" |
| `Method` | Metode/algoritma yang digunakan atau diusulkan | "RAG", "Cross-encoder Re-ranking", "LoRA" |
| `Dataset` | Dataset yang digunakan untuk evaluasi | "MS MARCO", "MMLU" |
| `Metric` | Metrik evaluasi | "F1 Score", "Recall@10" |
| `Finding` | Temuan atau klaim utama | "Re-ranking improves retrieval by 15%" |
| `Limitation` | Keterbatasan yang disebutkan | "Only tested on English queries" |

### 3.2 Jenis Relasi (Edge)

| Relasi | Dari → Ke | Contoh |
|---|---|---|
| `written_by` | Paper → Author | Paper ini ditulis oleh Chen |
| `affiliated_with` | Author → Institution | Chen berafiliasi dengan Stanford |
| `uses_method` | Paper → Method | Paper ini menggunakan metode RAG |
| `proposes_method` | Paper → Method | Paper ini mengusulkan metode baru |
| `uses_dataset` | Paper → Dataset | Paper ini menggunakan dataset MS MARCO |
| `uses_metric` | Paper → Metric | Paper ini menggunakan metrik F1 |
| `finds` | Paper → Finding | Paper ini menemukan bahwa... |
| `has_limitation` | Paper → Limitation | Paper ini memiliki keterbatasan... |
| `criticizes` | Paper → Method | Paper ini mengkritik metode X |
| `builds_on` | Paper → Method | Paper ini membangun di atas metode X |
| `compares` | Paper → Method | Paper ini membandingkan metode X dan Y |
| `same_author` | Paper → Paper | Paper A dan B punya author yang sama |

### 3.3 Prompt Template untuk Ekstraksi

Berikut prompt yang dikirim ke Gemini Flash untuk setiap chunk:

```
You are an academic paper analyzer. Your task is to extract entities and 
relationships from the following text chunk of an academic paper.

PAPER METADATA:
Title: {paper_title}
Year: {paper_year}
Venue: {paper_venue}

TEXT CHUNK:
{text_chunk}

RULES:
1. Only extract entities that are EXPLICITLY mentioned in the text.
2. Do NOT infer or assume relationships that are not clearly stated.
3. Be specific with method names — use the exact terminology from the paper.
4. Do NOT extract very generic terms like "the model", "the approach", 
   "the method", "the dataset" — only extract NAMED entities.
5. For findings, extract only MAJOR findings, not minor observations.
6. For limitations, only extract limitations that are EXPLICITLY stated 
   by the authors.
7. Do NOT extract entities from the references section.
8. Output MUST be valid JSON. No markdown, no explanation, just JSON.

OUTPUT FORMAT:
{
  "entities": [
    {
      "name": "exact name as mentioned in text",
      "type": "Paper|Author|Institution|Method|Dataset|Metric|Finding|Limitation"
    }
  ],
  "relationships": [
    {
      "source": "exact entity name",
      "target": "exact entity name",
      "type": "written_by|affiliated_with|uses_method|proposes_method|uses_dataset|uses_metric|finds|has_limitation|criticizes|builds_on|compares",
      "description": "brief description of this relationship"
    }
  ]
}
```

### 3.4 Penanganan Paper Metadata

Beberapa informasi tidak perlu diekstrak oleh LLM karena bisa di-parse langsung:

| Informasi | Cara Dapatkan |
|---|---|
| Judul paper | Halaman pertama PDF (teks terbesar di halaman 1) |
| Tahun | Dari judul atau header (format "(2024)") |
| Nama author | Dari halaman pertama, biasanya di bawah judul |
| Nama venue | Kadang di header atau footer halaman pertama |

Informasi ini **ditambahkan secara manual ke graph** tanpa memanggil LLM. LLM hanya mengekstrak hubungan semantik dari konten.

---

## 4. Tech Stack

| Komponen | Teknologi | Versi |
|---|---|---|
| Bahasa | Python | 3.11+ |
| PDF Parsing | PyMuPDF (`fitz`) | Latest |
| Chunking | LangChain `RecursiveCharacterTextSplitter` | Latest |
| LLM (Extraction) | Gemini 2.0 Flash | Via Google AI Studio (gratis) |
| Graph Storage | NetworkX | Latest |
| Visualisasi | Pyvis | Latest |
| Export | NetworkX GraphML | Built-in |

### 4.1 Dependencies (requirements.txt)

```
pymupdf
langchain
langchain-text-splitters
langchain-google-genai
google-generativeai
networkx
pyvis
```

### 4.2 Environment Variables

| Variable | Keterangan |
|---|---|
| `GEMINI_API_KEY` | API key dari Google AI Studio |

---

## 5. Struktur Proyek

```
graph-rag-explorer/
├── papers/                     # Folder untuk PDF paper (input user)
│   └── .gitkeep
├── app/
│   ├── __init__.py
│   ├── config.py               # Konfigurasi: schema, warna, API key
│   ├── pdf_parser.py           # Tahap 1: Parse PDF dengan PyMuPDF
│   ├── section_filter.py       # Tahap 2: Filter bagian relevan
│   ├── chunker.py              # Tahap 3: Pecah jadi chunk
│   ├── extractor.py            # Tahap 4: Ekstraksi entitas via Gemini
│   ├── graph_builder.py        # Tahap 5 & 6: Merge, deduplicate, build graph
│   ├── visualizer.py           # Tahap 7: Visualisasi dengan Pyvis
│   └── main.py                 # Script utama, menjalankan seluruh pipeline
├── output/
│   ├── extractions/            # JSON mentah hasil ekstraksi per paper
│   │   └── .gitkeep
│   ├── graph.html              # Visualisasi interaktif (output utama)
│   └── graph.graphml           # Graph data (bisa dibuka lagi nanti)
├── requirements.txt
└── README.md
```

---

## 6. Detail Implementasi Per File

### 6.1 `config.py`

Konfigurasi global:

```python
# Gemini API
GEMINI_MODEL = "gemini-2.0-flash"

# Chunking
CHUNK_SIZE = 3500
CHUNK_OVERLAP = 500

# Section filter
SECTIONS_TO_SKIP = ["references", "bibliography", "appendix", "acknowledgments", "acknowledgement"]

# Node colors
NODE_COLORS = {
    "Paper": "#4A90D9",
    "Author": "#E74C3C",
    "Institution": "#2C3E50",
    "Method": "#2ECC71",
    "Dataset": "#F39C12",
    "Metric": "#E67E22",
    "Finding": "#9B59B6",
    "Limitation": "#95A5A6",
}

# Deduplication
ENTITY_SIMILARITY_THRESHOLD = 0.8

# Valid entity types
VALID_ENTITY_TYPES = ["Paper", "Author", "Institution", "Method", "Dataset", "Metric", "Finding", "Limitation"]

# Valid relationship types
VALID_RELATIONSHIP_TYPES = [
    "written_by", "affiliated_with", "uses_method", "proposes_method",
    "uses_dataset", "uses_metric", "finds", "has_limitation",
    "criticizes", "builds_on", "compares", "same_author"
]
```

### 6.2 `pdf_parser.py`

**Fungsi:** `parse_pdf(file_path: str) -> dict`

- Input: path ke file PDF
- Output:
```python
{
    "title": "Judul Paper",
    "text_by_page": {0: "teks halaman 1", 1: "teks halaman 2", ...},
    "full_text": "teks gabungan seluruh halaman",
    "total_pages": 15
}
```

- Gunakan `fitz.open(file_path)` untuk membaca PDF
- Ekstrak teks per halaman dengan `page.get_text()`
- Judul diambil dari halaman pertama (teks dengan font size terbesar, atau baris pertama)
- Tangani error: file bukan PDF, file kosong, PDF terproteksi

### 6.3 `section_filter.py`

**Fungsi:** `filter_sections(text_by_page: dict, total_pages: int) -> str`

- Input: teks per halaman dari pdf_parser
- Output: teks gabungan setelah bagian yang tidak relevan dihapus
- Logika: scan setiap halaman, jika menemukan baris yang isinya hanya "References" atau "Appendix" (case-insensitive), hentikan proses dan kembalikan teks yang sudah dikumpulkan
- Juga hapus halaman yang isinya kurang dari 100 karakter (biasanya halaman kosong atau hanya berisi nomor halaman)

### 6.4 `chunker.py`

**Fungsi:** `chunk_text(text: str) -> list[str]`

- Input: teks bersih dari section_filter
- Output: list of chunk strings
- Gunakan `RecursiveCharacterTextSplitter` dari LangChain
- Parameter: `chunk_size=3500`, `chunk_overlap=500`, `separators=["\n\n", "\n", ". ", " "]`

### 6.5 `extractor.py`

**Fungsi:** `extract_from_chunk(chunk: str, paper_title: str, paper_year: str, paper_venue: str) -> dict`

- Input: satu chunk teks + metadata paper
- Output: JSON dengan format `{ "entities": [...], "relationships": [...] }`
- Panggil Gemini 2.0 Flash dengan prompt dari Bagian 3.3
- **Parsing response**: LLM kadang mengembalikan JSON yang tidak valid. Handle error:
  - Jika respons bukan JSON valid, coba parse ulang (strip markdown code block jika ada)
  - Jika tetap gagal, log error dan skip chunk tersebut (jangan crash)
  - Validasi bahwa entity types dan relationship types sesuai schema
- **Rate limiting**: tambah jeda 1 detik antar panggilan API untuk menghindari rate limit Gemini

**Fungsi tambahan:** `extract_from_paper(paper_data: dict) -> dict`

- Wrapper yang menjalankan seluruh pipeline untuk satu paper: parse → filter → chunk → extract per chunk → gabungkan semua hasil

### 6.6 `graph_builder.py`

**Fungsi:** `build_graph(all_extractions: list[dict]) -> nx.Graph`

- Input: list of JSON hasil ekstraksi dari semua paper
- Proses:
  1. Gabungkan semua entities dari semua paper
  2. **Deduplicate entities:**
     - Normalisasi: lowercase, strip, hapus karakter non-alphanumeric di tepi
     - Bandingkan dengan `difflib.SequenceMatcher(None, a, b).ratio()`
     - Jika ratio >= 0.8, gabungkan ke satu entitas (pakai nama yang lebih panjang/lebih deskriptif)
  3. **Deduplicate relationships:**
     - Hapus edge duplikat (source + target + type yang sama)
  4. **Tambahkan paper nodes:**
     - Setiap paper yang diekstrak harus punya node "Paper" sendiri
     - Hubungkan paper node ke entitas lain berdasarkan extractions
  5. **Tambahkan edge "same_author":**
     - Jika dua paper punya author yang sama, tambahkan edge `same_author`
  6. Buat NetworkX graph:
     - Node atribut: `type`, `label` (nama tampilan), `source_paper`, `source_page`
     - Edge atribut: `type`, `label` (jenis relasi), `description`, `source_paper`
- Return: NetworkX Graph object

**Fungsi tambahan:** `save_graph(graph: nx.Graph, output_path: str)`

- Simpan graph ke file GraphML
- Juga simpan JSON mentah ke `output/extractions/`

**Fungsi tambahan:** `load_graph(graphml_path: str) -> nx.Graph`

- Muat graph dari file GraphML (untuk me-skip ekstraksi jika sudah pernah dijalankan)

### 6.7 `visualizer.py`

**Fungsi:** `visualize(graph: nx.Graph, output_path: str)`

- Input: NetworkX Graph
- Output: file HTML di `output_path`
- Konfigurasi Pyvis:
  - `height="750px"`, `width="100%"`
  - `directed=False` (graph tidak berarah untuk kemudahan visualisasi)
  - Warna node berdasarkan `NODE_COLORS` di config
  - Label node: nama entitas
  - Label edge: jenis relasi (tampilkan saat hover)
  - Fisika: gunakan preset physics yang stabil (node tidak terus bergerak)
  - Cluster: node dengan tipe sama dikelompokkan berdekatan
- Font: gunakan font yang mendukung karakter khusus akademik (unicode)
- Background: putih atau sangat terang (#FAFAFA)
- Opsi tambahan: tombol "Reset View" untuk kembali ke layout awal

### 6.8 `main.py`

Script utama yang menjalankan seluruh pipeline:

```python
# Pseudocode alur:
1. Scan folder papers/ untuk file PDF
2. Untuk setiap PDF:
   a. Cek apakah sudah pernah diekstrak (file JSON ada di output/extractions/)
   b. Kalau belum: jalankan extract_from_paper()
   c. Kalau sudah: muat dari file JSON
3. Gabungkan semua extractions
4. Build graph dengan graph_builder.build_graph()
5. Simpan graph ke graph.graphml
6. Visualisasi dengan visualizer.visualize()
7. Print ringkasan: jumlah node, jumlah edge, jumlah per paper
8. Buka graph.html di browser (opsional, gunakan webbrowser.open())
```

---

## 7. Error Handling

### 7.1 PDF Parsing Error

- File bukan PDF → print error, skip file
- PDF terproteksi/password → print error, skip file
- PDF kosong → print warning, skip file

### 7.2 LLM Extraction Error

- API key tidak valid → print error, hentikan program
- Rate limit → tunggu 5 detik, coba ulang. Jika 3x gagal, skip chunk
- Respons bukan JSON valid → log respons asli ke file, skip chunk
- Respons kosong → skip chunk

### 7.3 Graph Building Error

- Entitas tanpa tipe → skip entitas
- Relasi ke entitas yang tidak ada → skip relasi
- Self-loop (relasi dari node ke dirinya sendiri) → hapus

### 7.4 Prinsip Umum

- **Jangan crash** — error pada satu paper/chunk tidak boleh menghentikan seluruh pipeline
- **Log semua error** — simpan ke file log, bukan hanya print ke console
- **Graceful degradation** — kalau beberapa chunk gagal, tetap bangun graph dari yang berhasil

---

## 8. Output yang Diharapkan

### 8.1 File Output

| File | Keterangan |
|---|---|
| `output/graph.html` | Visualisasi interaktif. Buka di browser. |
| `output/graph.graphml` | Data graph persisten. Bisa dibuka dengan NetworkX atau Gephi. |
| `output/extractions/paper_1.json` | Hasil ekstraksi mentah paper 1 |
| `output/extractions/paper_2.json` | Hasil ekstraksi mentah paper 2 |
| `...` | ... |
| `output/extraction_log.txt` | Log proses ekstraksi (error, skip, dll.) |

### 8.2 Console Output

Saat berjalan, program print progress:

```
Processing paper_1.pdf...
  Parsed 15 pages
  Filtered to 8 pages (removed References, Appendix)
  Created 3 chunks
  Extracting chunk 1/3... done (12 entities, 8 relationships)
  Extracting chunk 2/3... done (8 entities, 5 relationships)
  Extracting chunk 3/3... done (6 entities, 4 relationships)

Processing paper_2.pdf...
  ...

Building graph...
  Total entities: 67
  After deduplication: 52
  Total relationships: 89
  After deduplication: 64

Graph saved to output/graph.graphml
Visualization saved to output/graph.html

Summary:
  Papers: 5
  Nodes: 52
  Edges: 64
  Node types: Paper(5), Author(12), Method(8), Dataset(6), Finding(11), Limitation(4), Institution(6)
  Open output/graph.html in your browser.
```

### 8.3 Visualisasi yang Diharapkan

- Graph interaktif di browser
- Node berwarna berdasarkan tipe
- Bisa drag, zoom, klik node untuk melihat detail
- Edge terlihat saat hover
- Cluster node berdasarkan tipe (paper di satu area, method di area lain, dll.)
- Layout yang rapi dan tidak bertumpuk

---

## 9. Testing & Validasi

### 9.1 Validasi Manual

Setelah graph terbentuk, cek hal berikut:

1. **Setiap paper punya node** — jumlah node tipe "Paper" harus sama dengan jumlah PDF
2. **Author terhubung ke paper** — setiap paper seharusnya punya edge ke minimal 1 author
3. **Tidak ada node "the method" atau "the model"** — tanda extraction tidak tepat
4. **Edge "criticizes" masuk akal** — cek apakah paper benar-benar mengkritik metode tersebut
5. **Tidak ada node yang terisolasi** (tidak punya edge sama sekali) — kecuali memang benar-benar tidak terhubung

### 9.2 Debugging Extraction

Kalau graph terlihat salah:
1. Buka file JSON di `output/extractions/`
2. Cek chunk mana yang menghasilkan entitas/relasi yang salah
3. Baca chunk asli dan bandingkan dengan hasil ekstraksi
4. Sesuaikan prompt di `config.py` atau `extractor.py` jika perlu
5. Jalankan ulang extraction untuk paper tersebut saja (tanpa memproses ulang yang lain)

### 9.3 Incremental Processing

Program harus support menjalankan ulang tanpa memproses ulang paper yang sudah berhasil diekstrak:
- Cek: apakah file `output/extractions/paper_X.json` sudah ada?
- Kalau ya: muat dari file, tidak panggil LLM lagi
- Kalau tidak: proses seperti biasa
- Untuk force re-extract: hapus file JSON di `output/extractions/` atau tambahkan flag `--force`

---

## 10. Pertimbangan Penting

### 10.1 Kualitas Graph Sangat Bergantung pada Kualitas Paper

- Paper yang ditulis jelas dengan struktur bagus → ekstraksi akurat
- Paper yang bahasanya ambigu atau terlalu padat → ekstraksi kurang akurat
- Paper review/survey (40+ halaman) → terlalu banyak entitas, graph bisa ramai
- Paper pendek (8-12 halaman, conference paper) → paling ideal

### 10.2 Graph Tidak Akan 100% Akurat

Ini konsekuensi dari ekstraksi otomatis. Toleransi yang realistis: 80-85% akurasi. Beberapa edge mungkin salah, beberapa entitas mungkin terduplikasi. Ini acceptable untuk learning project.

### 10.3 Schema Generic Bisa Dievolusi

Schema di Bagian 3 bersifat generic (berlaku untuk topik apapun). Untuk akurasi lebih tinggi di topik spesifik, schema bisa di-tailor:

```python
# Contoh: schema khusus topik RAG
RAG_SPECIFIC_ENTITY_TYPES = [
    "Paper", "Author", "Institution",
    "RAG_Variant",      # mengganti Method yang generik
    "Embedding_Model",  # spesifik untuk RAG
    "Vector_DB",        # spesifik untuk RAG
    "Evaluation_Dataset",
    "Metric",
    "Finding",
    "Limitation"
]
```

Ini tidak mengubah arsitektur, hanya mengubah prompt dan config.

---

## 11. Roadmap Upgrade (Untuk Dipecah Nanti, Bukan Sekarang)

### Versi 2: Tambah Chatbot
- Tambah query endpoint
- Graph traversal untuk menjawab pertanyaan multi-hop
- LLM generate jawaban berdasarkan konteks dari graph

### Versi 3: Detail Panel
- Klik node → tampilkan detail (judul paper, author, ringkasan)
- Klik edge → tampilkan deskripsi relasi

### Versi 4: Deployment Online
- Ganti NetworkX dengan Neo4j (graph database)
- Deploy ke Knative (seperti chatbot RAG)
- Tambah fitur upload paper baru via web

### Versi 5: Hybrid (Vector + Graph RAG)
- Kombinasikan vector search dengan graph traversal
- Untuk pertanyaan yang butuh konten detail: vector search
- Untuk pertanyaan yang butuh hubungan: graph traversal