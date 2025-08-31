import os, math, re
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("MYSQL_URL")
TABLE = os.getenv("TABLE_NAME", "data_timbang")
INDEX_CANDIDATES = [c.strip() for c in os.getenv("INDEX_CANDIDATES", "").split(",") if c.strip()]

engine = create_engine(DB_URL, pool_pre_ping=True)

# --- helpers ----------------------------------------------------------------
def round_size(n: int) -> int:
    """Bikin ukuran VARCHAR yang 'aman' dan rapi (min 32, max 255, kelipatan 10)."""
    if n <= 0: return 32
    n = max(32, n * 2)             # buffer ×2
    n = int(math.ceil(n / 10.0) * 10)
    return min(n, 255)

def likely_time(colname: str) -> bool:
    return bool(re.search(r"\b(jam|time|waktu)\b", colname, re.IGNORECASE))

def print_header(title):
    print("\n" + "="*len(title))
    print(title)
    print("="*len(title))

# --- 1) ambil kolom TEXT / TINYTEXT / MEDIUMTEXT / LONGTEXT -----------------
with engine.connect() as con:
    cols = con.execute(text("""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = :t
          AND DATA_TYPE IN ('text','tinytext','mediumtext','longtext');
    """), {"t": TABLE}).mappings().all()

if not cols:
    print(f"[INFO] Tidak ada kolom TEXT di `{TABLE}`. (Mungkin sudah VARCHAR semua?)")
    exit(0)

print_header(f"Kolom TEXT yang terdeteksi di `{TABLE}`")
for c in cols:
    print(f"- {c['COLUMN_NAME']} ({c['DATA_TYPE']})")

# --- 2) ukur panjang real & rekomendasikan tipe -----------------------------
recs = []
with engine.connect() as con:
    for c in cols:
        col = c["COLUMN_NAME"]
        # hitung panjang maksimum di SQL (cepat & hemat memori)
        row = con.execute(text(f"""
            SELECT
              MAX(CHAR_LENGTH(`{col}`)) AS max_len,
              SUM(CASE WHEN `{col}` IS NULL OR `{col}`='' THEN 0 ELSE 1 END) AS non_nulls
            FROM `{TABLE}`;
        """)).mappings().one()
        max_len = int(row["max_len"] or 0)
        non_nulls = int(row["non_nulls"] or 0)

        # deteksi cepat kolom TIME jika namanya mengandung "Jam"
        time_suggestion = False
        if likely_time(col) and max_len in (4,5,7,8):  # "9:30", "09:30", "09:30:00"
            # cek sampel format HH:MM(:SS)
            has_bad = con.execute(text(f"""
                SELECT EXISTS(
                  SELECT 1 FROM `{TABLE}`
                  WHERE `{col}` IS NOT NULL AND `{col}` <> ''
                    AND `{col}` NOT REGEXP '^[0-2]?[0-9]:[0-5][0-9](:[0-5][0-9])?$'
                  LIMIT 1
                ) bad
            """)).scalar()
            if not has_bad:
                time_suggestion = True

        if time_suggestion:
            recs.append({
                "column": col,
                "from": "TEXT",
                "to": "TIME",
                "reason": "Semua nilai cocok pola HH:MM(:SS), lebih tepat TIME",
                "index_ok": True
            })
        else:
            size = round_size(max_len)
            recs.append({
                "column": col,
                "from": "TEXT",
                "to": f"VARCHAR({size})",
                "reason": f"max_len={max_len}, pakai buffer ×2 → {size}",
                "index_ok": True
            })

# --- 3) cetak ALTER TABLE yang direkomendasikan -----------------------------
print_header("REKOMENDASI ALTER TABLE (copy-paste ke MySQL)")
print(f"ALTER TABLE `{TABLE}`")
for i, r in enumerate(recs):
    comma = "," if i < len(recs)-1 else ";"
    print(f"  MODIFY COLUMN `{r['column']}` {r['to']}{comma}  -- {r['reason']}")

# --- 4) saran INDEX (hanya kalau kolomnya ada & bukan TEXT lagi) ------------
print_header("SARAN INDEX (opsional, setelah ALTER dijalankan)")
with engine.connect() as con:
    existing_cols = set(
        x["COLUMN_NAME"] for x in con.execute(text("""
            SELECT COLUMN_NAME FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t
        """), {"t": TABLE}).mappings().all()
    )
candidates = [c for c in INDEX_CANDIDATES if c in existing_cols]
if not candidates:
    print("(Tidak ada kandidat index dari INDEX_CANDIDATES yang cocok dengan kolom di tabel.)")
else:
    for c in candidates:
        print(f"CREATE INDEX idx_{c.lower()} ON `{TABLE}` (`{c}`);")

print("\n[NOTE] Jalankan ALTER TABLE dulu. Setelah sukses, jalankan CREATE INDEX di kolom yang sering dipakai filter.")
