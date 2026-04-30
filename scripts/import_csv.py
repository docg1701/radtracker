"""
Import production data from CSV files into the SQLite database.

CSV format (from temp/):
  Column 0: Data (day 1–31)
  Column 1: Nome (ressonâncias, outras tomografias, angiotomografias, tc abdome total, radiografias)
  Column 2: Quantidade (integer)
  Column 3: Modalidade (rm, tc, ag, tt, rx)

Mapping rules:
  - rm         → rm_count
  - tc + ag    → tc_count  (angiotc = same as regular tc)
  - tt × 2     → tc_count  (tc abdome total = 2× regular tc)
  - rx         → rx_count

Two sources per month (assemed + radiplan) are summed together per day.

Usage:
  python scripts/import_csv.py
"""

import csv
import glob
import os
import sqlite3
from collections import defaultdict
from datetime import datetime

DB_PATH = "data/telerrad.db"
CSV_DIR = "temp"


def parse_csv(filepath: str) -> dict[str, dict[str, int]]:
    """Parse one CSV file, return {date_str: {"rm": n, "tc": n, "ag": n, "tt": n, "rx": n}}."""
    rows: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    month = _infer_month(filepath)

    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for line in reader:
            if len(line) < 4:
                continue
            day = line[0].strip()
            if not day.isdigit():
                continue
            modality = line[3].strip().lower()
            if modality not in ("rm", "tc", "ag", "tt", "rx"):
                continue
            count_str = line[2].strip()
            if not count_str.isdigit():
                continue
            count = int(count_str)
            if count == 0:
                continue
            date_str = f"{month}-{int(day):02d}"
            rows[date_str][modality] += count

    return dict(rows)


def _infer_month(filepath: str) -> str:
    """Extract YYYY-MM from filename like 'assemed-2026 - janeiro.csv'."""
    basename = os.path.basename(filepath)
    # Format: "assemed-2026 - janeiro.csv" or "radiplan-2026 - março.csv"
    # Split on " - "
    parts = basename.split(" - ")
    year_str = parts[0].split("-")[-1]  # "assemed-2026" → "2026"
    month_name = parts[1].replace(".csv", "").strip()
    months_pt: dict[str, str] = {
        "janeiro": "01", "fevereiro": "02", "março": "03", "abril": "04",
        "maio": "05", "junho": "06", "julho": "07", "agosto": "08",
        "setembro": "09", "outubro": "10", "novembro": "11", "dezembro": "12",
    }
    month_num = months_pt.get(month_name.lower(), "01")
    return f"{year_str}-{month_num}"


def combine_sources(assemed: dict, radiplan: dict) -> dict[str, dict[str, int]]:
    """Sum assemed + radiplan counts per day."""
    all_dates = set(assemed.keys()) | set(radiplan.keys())
    combined: dict[str, dict[str, int]] = {}
    for date_str in sorted(all_dates):
        combined[date_str] = {
            mod: assemed.get(date_str, {}).get(mod, 0)
            + radiplan.get(date_str, {}).get(mod, 0)
            for mod in ("rm", "tc", "ag", "tt", "rx")
        }
    return combined


def normalize(raw: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    """Apply mapping rules: ag→tc, tt→2×tc. Return {date: {rm_count, tc_count, rx_count}}."""
    result: dict[str, dict[str, int]] = {}
    for date_str, counts in sorted(raw.items()):
        rm = counts.get("rm", 0)
        tc = counts.get("tc", 0)
        ag = counts.get("ag", 0)
        tt = counts.get("tt", 0)
        rx = counts.get("rx", 0)
        tc_total = tc + ag + (tt * 2)
        if rm == 0 and tc_total == 0 and rx == 0:
            continue
        result[date_str] = {"rm_count": rm, "tc_count": tc_total, "rx_count": rx}
    return result


def upsert_daily(cursor: sqlite3.Cursor, date_str: str, rm: int, tc: int, rx: int) -> None:
    """Insert or update a daily production row."""
    cursor.execute(
        """
        INSERT INTO daily_production (date, rm_count, tc_count, rx_count, updated_at)
        VALUES (?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(date) DO UPDATE SET
            rm_count = excluded.rm_count,
            tc_count = excluded.tc_count,
            rx_count = excluded.rx_count,
            updated_at = datetime('now','localtime')
        """,
        (date_str, rm, tc, rx),
    )


def export_markdown(all_data: dict[str, dict[str, int]]) -> str:
    """Generate a Markdown report of the imported data."""
    lines = ["# Produção Importada\n"]
    lines.append(f"Importado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")

    total_rm = total_tc = total_rx = 0

    for date_str, counts in sorted(all_data.items()):
        rm = counts["rm_count"]
        tc = counts["tc_count"]
        rx = counts["rx_count"]
        total_rm += rm
        total_tc += tc
        total_rx += rx
        day_label = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
        lines.append(f"| {day_label} | {rm} | {tc} | {rx} |")

    lines.insert(3, "| Data | RM | TC | RX |")
    lines.insert(4, "|---|---|---|---|")
    lines.append(f"\n**Totais:** RM={total_rm} · TC={total_tc} · RX={total_rx}")
    return "\n".join(lines)


def main() -> None:
    csv_files = sorted(glob.glob(os.path.join(CSV_DIR, "*.csv")))
    if not csv_files:
        print("Nenhum CSV encontrado em temp/")
        return

    # Group files by month and source
    months: dict[str, dict[str, str]] = defaultdict(dict)
    for f in csv_files:
        basename = os.path.basename(f).lower()
        if "assemed" in basename:
            months[_infer_month(f)]["assemed"] = f
        elif "radiplan" in basename:
            months[_infer_month(f)]["radiplan"] = f

    all_normalized: dict[str, dict[str, int]] = {}

    for year_month, sources in sorted(months.items()):
        assemed = parse_csv(sources.get("assemed", "")) if "assemed" in sources else {}
        radiplan = parse_csv(sources.get("radiplan", "")) if "radiplan" in sources else {}
        combined = combine_sources(assemed, radiplan)
        normalized = normalize(combined)
        all_normalized.update(normalized)

    if not all_normalized:
        print("Nenhum dado encontrado nos CSVs.")
        return

    # ── Print summary ──
    print(f"Total de dias com dados: {len(all_normalized)}")
    total_rm = sum(v["rm_count"] for v in all_normalized.values())
    total_tc = sum(v["tc_count"] for v in all_normalized.values())
    total_rx = sum(v["rx_count"] for v in all_normalized.values())
    print(f"Totais: RM={total_rm} · TC={total_tc} · RX={total_rx}")

    # ── Export Markdown ──
    md = export_markdown(all_normalized)
    os.makedirs("data", exist_ok=True)
    md_path = "data/producao_importada.md"
    with open(md_path, "w") as f:
        f.write(md)
    print(f"Markdown salvo em: {md_path}")

    # ── Import into SQLite ──
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    inserted = 0
    updated = 0

    for date_str, counts in sorted(all_normalized.items()):
        cur.execute("SELECT COUNT(*) FROM daily_production WHERE date = ?", (date_str,))
        exists = cur.fetchone()[0] > 0
        upsert_daily(cur, date_str, counts["rm_count"], counts["tc_count"], counts["rx_count"])
        if exists:
            updated += 1
        else:
            inserted += 1

    db.commit()
    db.close()

    print(f"SQLite: {inserted} inseridos, {updated} atualizados em {DB_PATH}")


if __name__ == "__main__":
    main()
