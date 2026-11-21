# Tracely

**Tracely** adalah aplikasi desktop **Process Mining & Event Log Intelligence** untuk menganalisis file event log standar IEEE XES (`.xes` / `.xes.gz`). Dibangun menggunakan **Python, PM4Py, Pandas, dan PySide6** dengan antarmuka desktop bergaya *Professional Neubrutalism*.

## Fitur Utama

- **XES Event Log Ingestion & Validation**: Memuat file `.xes` dan `.xes.gz` via PM4Py dengan normalisasi timestamp UTC dan pengurutan trace deterministik.
- **Overview & Activity Frequency**: Ringkasan total case, total event, aktivitas unik, rata-rata *cycle time*, dan distribusi durasi case.
- **Process Outcomes & Throughput Segmentation**: Analisis outcome proses (positif, negatif, pembatalan akhir) serta segmentasi *Fast vs Slow Cases*.
- **Rework & Resource Analytics**: Deteksi pengulangan aktivitas berdasarkan `lifecycle:transition` dan analisis pengulangan oleh `org:resource` yang sama.
- **Event Sequence, Custom Rule Builder & Interactive DFG**: Analisis urutan *eventually-follows*, pembuat filter aturan dinamis, serta visualisasi **Directly-Follows Graph (Activity Map)** bergaya Disco lengkap dengan *bottleneck heatmap* dan animasi aliran token.
- **Case Explorer & Reports Export**: Inspeksi timeline kronologis per case, serta ekspor hasil analisis dan bukti case ke **CSV** (`analysis_summary.csv`, `case_evidence.csv`) dan **PDF**.

---

## Persyaratan

- Windows 10 / 11 (atau OS desktop yang mendukung Qt6)
- Python `>= 3.10` (direkomendasikan Python 3.11+)

---

## Cara Setup Project

1. **Clone repository**
   ```powershell
   git clone <URL_REPOSITORY_ANDA>
   cd Tracely
   ```

2. **Buat dan aktifkan virtual environment (`.venv`)**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements-dev.txt
   pip install -e .
   ```

   *(Jika PowerShell memblokir aktivasi `.venv`, Anda dapat menjalankan perintah langsung melalui `.\.venv\Scripts\python.exe -m pip install ...`)*

---

## Cara Menjalankan Aplikasi

```powershell
.\.venv\Scripts\python.exe -m app.main
```

1. Klik **Import Event Log** di bagian atas (atau buka menu **Projects**).
2. Pilih file `.xes` / `.xes.gz` Anda (atau gunakan data demo di `examples/synthetic_bpic17_demo.xes` untuk uji cepat).
3. Klik **Run All Analyses** untuk melihat hasil analisis, eksplorasi **Activity Map (DFG)**, periksa trace di **Case Explorer**, dan ekspor laporan ke CSV atau PDF.

---

## Menjalankan Unit Test

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

---

## Struktur Singkat

```text
Tracely/
├── app/                   # PySide6 desktop GUI & interactive DFG canvas
├── src/bpic17_analyzer/   # Core PM4Py/Pandas analysis engine & exporters
├── tests/                 # Automated unit & GUI integration tests
├── examples/              # Synthetic XES log for quick smoke testing
├── data/raw/              # Local XES datasets (ignored by Git)
└── exports/               # Default CSV & PDF export directory (ignored by Git)
```
