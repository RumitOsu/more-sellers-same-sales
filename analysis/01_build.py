"""Loads the raw CSV files into DuckDB and builds the one-row-per-order table."""
from db import RAW, DB, ROOT
import duckdb

FILES = {
    "orders": "olist_orders_dataset", "items": "olist_order_items_dataset",
    "pay": "olist_order_payments_dataset", "reviews": "olist_order_reviews_dataset",
    "customers": "olist_customers_dataset", "products": "olist_products_dataset",
    "sellers": "olist_sellers_dataset", "cat": "product_category_name_translation",
}
con = duckdb.connect(str(DB))
for name, f in FILES.items():
    con.execute(f"create or replace table {name} as select * from read_csv_auto('{(RAW / (f + '.csv')).as_posix()}', header=true)")
con.execute((ROOT / "analysis" / "01_model.sql").read_text(encoding="utf-8"))
n, lo, hi = con.execute("select count(*), min(purchased_at), max(purchased_at) from fact_orders").fetchone()
print(f"fact_orders: {n:,} orders from {lo} to {hi}")
