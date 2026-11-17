"""Shared helper: opens the DuckDB file the analysis scripts read and write."""
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "olist.duckdb"
RESULTS = ROOT / "results"

# The study window. 2016 holds a few hundred scattered orders and the file stops
# partway through September 2018, so both ends are left out.
START, END = "2017-01-01", "2018-09-01"

def connect(read_only=True):
    return duckdb.connect(str(DB), read_only=read_only)
