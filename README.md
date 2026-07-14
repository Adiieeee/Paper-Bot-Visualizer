# Graph RAG Academic Paper Explorer

Aplikasi lokal yang memproses PDF paper akademik, mengekstrak entitas dan relasi menggunakan Gemini Flash, lalu memvisualisasikannya sebagai knowledge graph interaktif.

## Cara Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Siapkan API key

Salin `.env.example` menjadi `.env` dan isi API key:

```bash
copy .env.example .env
```

Edit file `.env`:
```
GEMINI_API_KEY=api_key_kamu
```

Dapatkan API key gratis di: https://aistudio.google.com/apikey

### 3. Masukkan PDF

Taruh file PDF paper akademik ke folder `papers/`:

```
papers/
├── paper1.pdf
├── paper2.pdf
└── ...
```

## Cara Jalankan

```bash
python main.py
```

Output akan otomatis terbuka di browser sebagai `output/graph.html`.

### Opsi tambahan

```bash
# Paksa ekstraksi ulang semua paper (abaikan cache)
python main.py --force

# Jangan buka browser otomatis
python main.py --no-open

# Custom folder PDF
python main.py --papers-dir /path/ke/folder
```

## Cara Kerja

```
PDF → Parse → Filter Sections → Chunking → Gemini Extraction → Merge & Deduplicate → NetworkX Graph → Pyvis Visualization
```

1. **PDF Parser** — ekstrak teks per halaman menggunakan PyMuPDF
2. **Section Filter** — hapus References, Appendix, Acknowledgments
3. **Chunking** — pecah teks menjadi chunk ~3500 karakter
4. **Extraction** — Gemini Flash ekstrak entitas dan relasi per chunk
5. **Merge & Dedup** — gabungkan semua hasil, hapus duplikat
6. **Graph Builder** — bangun NetworkX graph
7. **Visualizer** — render sebagai HTML interaktif dengan Pyvis

## Output

| File | Keterangan |
|---|---|
| `output/graph.html` | Visualisasi interaktif — buka di browser |
| `output/graph.graphml` | Data graph — bisa dibuka dengan Gephi |
| `output/extractions/*.json` | Hasil ekstraksi mentah per paper |
| `output/extraction_log.txt` | Log detail proses |

## Tips

- **Paper yang ideal**: conference paper 8–12 halaman dengan struktur jelas
- **Tambah paper baru**: cukup tambah PDF ke folder `papers/` dan jalankan lagi — paper lama tidak akan diekstrak ulang
- **Ganti topik**: hapus `output/extractions/` dan ganti isi `papers/`, lalu jalankan ulang
- **Debug**: buka file JSON di `output/extractions/` untuk melihat hasil ekstraksi mentah

## Struktur Proyek

```
graph-rag-explorer/
├── papers/                    # Taruh PDF di sini
├── app/
│   ├── config.py              # Konfigurasi global
│   ├── pdf_parser.py          # Tahap 1: Parse PDF
│   ├── section_filter.py      # Tahap 2: Filter sections
│   ├── chunker.py             # Tahap 3: Chunking
│   ├── extractor.py           # Tahap 4: Ekstraksi via Gemini
│   ├── graph_builder.py       # Tahap 5 & 6: Build graph
│   └── visualizer.py          # Tahap 7: Visualisasi Pyvis
├── output/
│   └── extractions/
├── main.py                    # Entry point
├── requirements.txt
└── .env                       # API key (buat sendiri dari .env.example)
```
