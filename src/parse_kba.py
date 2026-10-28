"""Parse KBA FZ8 monthly workbooks into tidy tables.

FZ 8.2: new passenger-car registrations by brand, with battery-electric (BEV) and plug-in hybrid (PHEV) counts.
FZ 8.6: the same fuel split by federal state (Bundesland).

Columns are found by their header text, not by position, because KBA added columns over time (e.g. Euro 7).
A dash ("-") means zero. Output: data/clean/brand_month.csv and data/clean/state_month.csv.

Usage: python src/parse_kba.py data/raw
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def _num(v) -> int:
    if v is None:
        return 0
    s = str(v).strip().replace(".", "").replace(" ", "")
    if s in ("", "-", "–"):
        return 0
    return int(float(s.replace(",", ".")))


def _header_map(rows: list[tuple], first_data: int) -> dict[int, str]:
    """Column index -> lower-case header text, joined over the header rows above the first data row."""
    labels: dict[int, str] = {}
    for r in rows[max(0, first_data - 4):first_data]:
        last = ""
        for i, v in enumerate(r):
            text = re.sub(r"\s+", " ", str(v or "")).strip().lower()
            if text:
                last = text
            labels[i] = (labels.get(i, "") + " " + text).strip()
    return labels


def _find(labels: dict[int, str], *needles: str, exclude: str = "") -> int:
    for i, lab in labels.items():
        if all(n in lab for n in needles) and not (exclude and exclude in lab):
            return i
    raise KeyError(f"no column with {needles}")


def parse_sheet(ws, key_name: str, total_name: str) -> pd.DataFrame:
    rows = list(ws.iter_rows(values_only=True))
    first = next(i for i, r in enumerate(rows) if r and any(str(v or "").strip().lower() == key_name for v in r))
    key_col = next(i for i, v in enumerate(rows[first]) if str(v or "").strip().lower() == key_name)
    data_start = next(i for i in range(first + 1, len(rows)) if _looks_numeric(rows[i], key_col))
    labels = _header_map(rows, data_start)
    c_bev = _find(labels, "elektro (bev)")
    c_phev = _find(labels, "plug-in")
    c_total = (_find(labels, "anzahl") if key_name == "marke" else _find(labels, "insgesamt", exclude="benzin"))
    if key_name != "marke":  # state sheet: the last "insgesamt" column is the all-fuel total
        c_total = max(i for i, lab in labels.items() if lab.strip() == "insgesamt" or lab.endswith(" insgesamt") and "hybrid" not in lab and "benzin" not in lab and "diesel" not in lab)
    out = []
    for r in rows[data_start:]:
        name = str(r[key_col] or "").strip()
        if not name or name.startswith("©"):
            continue
        out.append({"name": name, "total": _num(r[c_total]), "bev": _num(r[c_bev]), "phev": _num(r[c_phev]),
                    "is_total": name.upper() == total_name})
    return pd.DataFrame(out)


def _looks_numeric(r, key_col) -> bool:
    return bool(r) and str(r[key_col] or "").strip() != "" and any(re.fullmatch(r"[\d.,-]+", str(v or "").strip() or "x") for v in r[key_col + 1:key_col + 3])


def parse_file(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    month = re.search(r"(\d{4})(\d{2})", path.name)
    period = f"{month.group(1)}-{month.group(2)}"
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    brands = parse_sheet(wb["FZ 8.2"], "marke", "INSGESAMT").assign(month=period)
    states = parse_sheet(wb["FZ 8.6"], "bundesland", "DEUTSCHLAND").assign(month=period)
    return brands, states


def main() -> None:
    raw = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "raw"
    b, s = zip(*(parse_file(p) for p in sorted(raw.glob("fz8_*.xlsx"))))
    brands, states = pd.concat(b), pd.concat(s)
    (ROOT / "data" / "clean").mkdir(parents=True, exist_ok=True)
    brands.to_csv(ROOT / "data" / "clean" / "brand_month.csv", index=False)
    states.to_csv(ROOT / "data" / "clean" / "state_month.csv", index=False)
    print(f"{brands.month.nunique()} months, {len(brands)} brand rows, {len(states)} state rows")


if __name__ == "__main__":
    main()
