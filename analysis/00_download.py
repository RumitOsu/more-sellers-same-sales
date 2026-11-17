"""Downloads the public Olist tables into data/raw. Nothing here needs an account or a key."""
from urllib.request import urlretrieve
from db import RAW

BASE = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/"
FILES = [
    "olist_customers_dataset", "olist_order_items_dataset", "olist_order_payments_dataset",
    "olist_order_reviews_dataset", "olist_orders_dataset", "olist_products_dataset",
    "olist_sellers_dataset", "product_category_name_translation",
]

RAW.mkdir(parents=True, exist_ok=True)
for name in FILES:
    target = RAW / f"{name}.csv"
    if target.exists():
        print("already have", target.name)
        continue
    urlretrieve(BASE + name + ".csv", target)
    print("downloaded", target.name, f"{target.stat().st_size / 1e6:.1f} MB")
