# CONFIG SCHEMA — config.yaml

Satu-satunya sumber konfigurasi UI. Dibaca oleh `core/config.py` saat
app start (`Config.load()`). Edit file ini untuk menambah/menyembunyikan
tool di sidebar — script-nya harus ada di folder root proyek.

## Struktur lengkap

```yaml
app:
  name: Bopel Automation Toolkit     # wajib, string tidak kosong
  version: "1.0.0"                   # wajib, string
  subtitle: Internal Warehouse Utilities  # wajib, string

tools:            # wajib, list (boleh kosong)
  - name: Checklist Automation       # wajib, string tidak kosong (label tombol sidebar)
    script: check.py                 # wajib, string tidak kosong (nama file di root)
    description: "Checklist pesanan dan validasi harga Shopee vs aplikasi"  # opsional, string
    # OPSIONAL — 1 tool bisa punya beberapa MODE eksekusi (baru, 2026-08-15):
    # UI merender 1 tombol per mode di halaman tool (tombol Start disembunyikan).
    # mode.script kosong = pakai script tool induk (scan.py).
    modes:
      - name: Scan Kecil             # wajib per mode, string tidak kosong
        description: "Data detail, jumlah sedikit"   # opsional, string
#   - name: Scan Bulanan  # (removed - mode no longer supported)  # (removed - mode no longer supported)
        script: scan_bulanan.py      # opsional, string (file di root)

logging:          # wajib, mapping
  level: INFO     # wajib, string (DEBUG/INFO/WARNING/ERROR)
  file: logs/app.log   # wajib, string

# Auto-Fetch Shopee (shopee_fetch.py) — daftar toko:
stores:           # opsional, list
  - name: Toko 1 — Toko Alkes Solo   # wajib, harus unik (dipakai UI pilih toko)
    enabled: true                    # wajib, bool
    shortcut: C:\Users\PC\Desktop\Toko Alkes Solo.lnk   # wajib utk toko enabled
    akun: tokoalkessolo              # WAJIB utk fetch multi-toko: nama akun Shopee
                                     # (muncul di sidebar seller center). Dipakai
                                     # verifikasi identitas window sebelum fetch.
    chrome_user_data_dir: ...        # dokumentasi saja (dari isi .lnk)
    profile_directory: Profile 7     # dokumentasi saja (dari isi .lnk)
```

## Contoh valid terkecil

```yaml
app:
  name: Bopel Automation Toolkit
  version: "1.0.0"
  subtitle: Internal Warehouse Utilities
tools: []
logging:
  level: INFO
  file: logs/app.log
```

## Aturan tipe data

| Field | Tipe | Wajib | Catatan |
|---|---|---|---|
| `app` | mapping | ya | |
| `app.name` | string | ya | tidak boleh kosong |
| `app.version` | string | ya | |
| `app.subtitle` | string | ya | |
| `tools` | list | ya | boleh kosong = sidebar tanpa tombol tool |
| `tools[].name` | string | ya | tidak boleh kosong = label tombol |
| `tools[].script` | string | ya | tidak boleh kosong; launcher cek file ada saat Start |
| `tools[].description` | string | opsional | penjelasan utama di halaman tool |
| `logging` | mapping | ya | |
| `logging.level` | string | ya | |
| `logging.file` | string | ya | |

## Apa yang terjadi kalau field salah/hilang?

Sejak 2026-08-12 validasi dibuat **ketat dan eksplisit** di
`Config.load()` (sebelumnya SILENT FAIL: field salah diabaikan diam-diam
→ sidebar kosong tanpa pesan, atau crash aneh saat klik tool):

- Field wajib hilang / salah tipe / string kosong → app **TIDAK start**,
  terminal menampilkan pesan error jelas, contoh:

```
❌ config.yaml ('C:\robot\bopel\config.yaml') tidak valid:
  - tools[0].script: wajib string tidak kosong
  - app.name: wajib string
Perbaiki file config dulu (lihat docs/CONFIG_SCHEMA.md), lalu jalankan lagi.
```

- `config.yaml` tidak ada sama sekali → dibuat otomatis dari default yang
  valid (tidak error, hanya warning tersirat saat file baru dibuat).
- YAML tidak bisa di-parse (syntax rusak) → error Python `yaml` akan
  keluar di terminal (pesan parser YAML), bukan app jalan dengan config
  kosong.
- `tools[].script` menunjuk file yang tidak ada → error muncul SAAT klik
  Start di UI ("Script not found"), bukan saat start app.

## Catatan

- Nama tool di `name` bebas (boleh spasi); `script` HARUS persis nama
  file di root proyek (contoh `check.py`).
- Tidak perlu restart app setelah edit — tapi app saat ini belum reload
  config otomatis, jadi restart (tutup & jalankan `start.bat` lagi).