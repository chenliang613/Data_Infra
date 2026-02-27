#!/usr/bin/env python3
"""Generate sample CSV data files for the demo."""
import csv
import random
from pathlib import Path

ASSETS_DIR = Path(__file__).parent.parent / "data" / "assets"


def generate_user_behavior_csv():
    path = ASSETS_DIR / "user_behavior.csv"
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["user_id", "email", "phone", "page", "duration_sec", "event", "timestamp"],
        )
        writer.writeheader()
        events = ["pageview", "click", "purchase", "search"]
        pages = ["/home", "/products", "/cart", "/checkout", "/profile"]
        for i in range(5000):
            writer.writerow({
                "user_id": f"u{i:05d}",
                "email": f"user{i}@example.com",
                "phone": f"138{random.randint(10000000, 99999999)}",
                "page": random.choice(pages),
                "duration_sec": random.randint(5, 300),
                "event": random.choice(events),
                "timestamp": f"2026-02-{random.randint(1,28):02d}T{random.randint(0,23):02d}:{random.randint(0,59):02d}:00Z",
            })
    print(f"✅ 生成用户行为数据: {path} (5000 行)")


def generate_product_catalog_csv():
    path = ASSETS_DIR / "product_catalog.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["product_id", "name", "category", "price", "stock", "supplier"],
        )
        writer.writeheader()
        categories = ["电子", "服装", "食品", "家居", "运动"]
        for i in range(1000):
            writer.writerow({
                "product_id": f"P{i:04d}",
                "name": f"商品_{i}",
                "category": random.choice(categories),
                "price": round(random.uniform(9.9, 9999.0), 2),
                "stock": random.randint(0, 500),
                "supplier": f"供应商_{i % 50}",
            })
    print(f"✅ 生成商品目录数据: {path} (1000 行)")


if __name__ == "__main__":
    generate_user_behavior_csv()
    generate_product_catalog_csv()
