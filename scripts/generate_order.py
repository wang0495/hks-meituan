"""
生成 2026 年珠海/广州/湛江 POI 交通流量模拟数据
公式: ts = base_value × holiday_factor × weekday_factor × seasonal_factor + noise
"""

import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ============== 配置 ==============

# 2026 年中国法定节假日
# key: date, value: dict{category: multiplier}
HOLIDAYS: dict[date, dict[str, float]] = {
    # 元旦
    date(2026, 1, 1): {"default": 1.3, "餐饮": 1.4},
    date(2026, 1, 2): {"default": 1.3, "餐饮": 1.4},
    date(2026, 1, 3): {"default": 1.3, "餐饮": 1.4},
    # 春节 (2/17-23)
    date(2026, 2, 17): {"default": 2.0, "餐饮": 2.5, "酒店": 1.8},
    date(2026, 2, 18): {"default": 2.0, "餐饮": 2.5, "酒店": 1.8},
    date(2026, 2, 19): {"default": 1.8, "餐饮": 2.3, "酒店": 1.7},
    date(2026, 2, 20): {"default": 1.6, "餐饮": 2.0, "酒店": 1.6},
    date(2026, 2, 21): {"default": 1.5, "餐饮": 1.8, "酒店": 1.5},
    date(2026, 2, 22): {"default": 1.4, "餐饮": 1.6, "酒店": 1.4},
    date(2026, 2, 23): {"default": 1.3, "餐饮": 1.5},
    # 清明 (4/4-6)
    date(2026, 4, 4): {"default": 1.4, "餐饮": 1.5},
    date(2026, 4, 5): {"default": 1.5, "餐饮": 1.6},
    date(2026, 4, 6): {"default": 1.4, "餐饮": 1.5},
    # 五一 (5/1-5)
    date(2026, 5, 1): {"default": 1.6, "餐饮": 1.7},
    date(2026, 5, 2): {"default": 1.7, "餐饮": 1.8},
    date(2026, 5, 3): {"default": 1.7, "餐饮": 1.8},
    date(2026, 5, 4): {"default": 1.5, "餐饮": 1.6},
    date(2026, 5, 5): {"default": 1.4, "餐饮": 1.5},
    # 端午 (6/19-21)
    date(2026, 6, 19): {"default": 1.4, "餐饮": 1.5},
    date(2026, 6, 20): {"default": 1.5, "餐饮": 1.6},
    date(2026, 6, 21): {"default": 1.4, "餐饮": 1.5},
    # 中秋+国庆 (10/1-8) 调休共8天
    date(2026, 10, 1): {"default": 2.2, "餐饮": 2.5, "酒店": 2.2},
    date(2026, 10, 2): {"default": 2.2, "餐饮": 2.5, "酒店": 2.2},
    date(2026, 10, 3): {"default": 2.0, "餐饮": 2.3, "酒店": 2.0},
    date(2026, 10, 4): {"default": 1.8, "餐饮": 2.1, "酒店": 1.8},
    date(2026, 10, 5): {"default": 1.7, "餐饮": 2.0, "酒店": 1.7},
    date(2026, 10, 6): {"default": 1.5, "餐饮": 1.8, "酒店": 1.5},
    date(2026, 10, 7): {"default": 1.4, "餐饮": 1.6},
    date(2026, 10, 8): {"default": 1.3, "餐饮": 1.5},
}

# 品类配置: (日均基数, 周末因子[Mon-Sun], 季节振幅, 噪声std)
CATEGORY_CFG: dict[str, tuple[int, list[float], float, float]] = {
    "餐饮": (300, [1.0, 1.0, 1.0, 1.0, 1.10, 1.25, 1.20], 0.15, 0.10),
    "购物": (150, [1.0, 1.0, 1.0, 1.0, 1.15, 1.40, 1.35], 0.20, 0.12),
    "酒店": (40,  [1.0, 1.0, 1.0, 1.0, 1.30, 1.50, 1.20], 0.25, 0.15),
    "文化": (80,  [1.0, 1.0, 1.0, 1.0, 1.10, 1.45, 1.40], 0.20, 0.12),
    "运动": (60,  [1.0, 1.0, 1.0, 1.0, 1.15, 1.40, 1.35], 0.15, 0.14),
    "其他": (50,  [1.0, 1.0, 1.0, 1.0, 1.10, 1.20, 1.15], 0.10, 0.10),
}

# 城市倍率
CITY_MULT: dict[str, float] = {"珠海": 1.0, "广州": 1.15, "湛江": 0.85}

# 小时分布 (24 个值, 和为 1.0)
HOURLY_PROFILES: dict[str, list[float]] = {
    "餐饮": [0.01,0.00,0.00,0.00,0.01,0.02,0.04,0.06,0.07,0.06,0.09,0.12,0.11,0.06,0.04,0.03,0.04,0.07,0.10,0.09,0.06,0.04,0.02,0.01],
    "购物": [0.00,0.00,0.00,0.00,0.00,0.01,0.02,0.04,0.06,0.08,0.10,0.10,0.08,0.06,0.08,0.10,0.10,0.08,0.05,0.03,0.01,0.00,0.00,0.00],
    "酒店": [0.01,0.00,0.00,0.00,0.00,0.01,0.03,0.06,0.09,0.10,0.08,0.06,0.04,0.06,0.12,0.14,0.10,0.06,0.04,0.03,0.02,0.02,0.02,0.01],
    "文化": [0.00,0.00,0.00,0.00,0.00,0.00,0.01,0.03,0.06,0.10,0.14,0.14,0.10,0.08,0.12,0.12,0.06,0.03,0.01,0.00,0.00,0.00,0.00,0.00],
    "运动": [0.00,0.00,0.00,0.00,0.01,0.03,0.06,0.10,0.12,0.10,0.08,0.06,0.04,0.03,0.04,0.06,0.10,0.12,0.08,0.04,0.02,0.01,0.00,0.00],
    "其他": [0.01,0.00,0.00,0.00,0.01,0.02,0.04,0.06,0.07,0.07,0.08,0.09,0.08,0.06,0.06,0.07,0.08,0.07,0.05,0.04,0.02,0.01,0.01,0.01],
}

START_DATE = date(2026, 1, 1)
END_DATE = date(2026, 12, 31)


def gen_date_range(start: date, end: date) -> list[date]:
    delta = (end - start).days + 1
    return [start + timedelta(days=i) for i in range(delta)]


def get_holiday_factor(d: date, cat: str) -> float:
    if d not in HOLIDAYS:
        return 1.0
    entry = HOLIDAYS[d]
    return entry.get(cat, entry.get("default", 1.0))


def get_weekday_factor(d: date, cat: str) -> float:
    weekday_vals = CATEGORY_CFG[cat][1]  # [Mon, Tue, ..., Sun]
    return weekday_vals[d.weekday()]


def get_seasonal_factor(d: date, cat: str) -> float:
    """sin(2π * day_of_year / 365) 夏季/冬季波动"""
    day_of_year = (d - START_DATE).days
    amplitude = CATEGORY_CFG[cat][2]
    return 1.0 + amplitude * math.sin(2 * math.pi * day_of_year / 365)


def gen_cat_city_series(cat: str, city: str) -> np.ndarray:
    """生成某个品类×城市的 365 天日级数据"""
    base = CATEGORY_CFG[cat][0]
    city_mult = CITY_MULT[city]
    noise_std = CATEGORY_CFG[cat][3]

    dates = gen_date_range(START_DATE, END_DATE)
    n = len(dates)

    np.random.seed(hash(f"{cat}_{city}") & 0xFFFFFFFF)
    noise = np.random.normal(0, noise_std * base, n)

    values = np.zeros(n)
    for i, d in enumerate(dates):
        hf = get_holiday_factor(d, cat)
        wf = get_weekday_factor(d, cat)
        sf = get_seasonal_factor(d, cat)
        values[i] = base * city_mult * hf * wf * sf + noise[i]

    return np.maximum(values, 1).round().astype(int)


def calc_popularity(poi: dict) -> float:
    """根据 POI 属性计算 popularity 系数 [0.3, 2.0]"""
    cat = poi.get("category", "其他")
    price_max = {"餐饮": 300, "购物": 500, "酒店": 1500, "文化": 200, "运动": 300, "其他": 200}.get(cat, 200)

    rating_norm = max(0, (poi.get("rating", 3.5) - 3.0) / 2.0)
    price_norm = min(1.0, poi.get("avg_price", 50) / price_max)
    queue_bonus = 0.2 if poi.get("queue_prone") else 0.0
    stay_norm = poi.get("avg_stay_min", 60) / 120.0

    pop = 0.4 * rating_norm + 0.3 * price_norm + 0.2 * queue_bonus + 0.1 * stay_norm
    return max(0.3, min(2.0, 0.5 + pop))


def main():
    # 读取 POI 数据
    poi_path = Path(__file__).parent.parent / "backend" / "data" / "city_poi_db.json"
    pois = json.loads(poi_path.read_text(encoding="utf-8"))
    print(f"Loaded {len(pois)} POIs")

    # 生成 15 条品类×城市日级序列
    series_map: dict[tuple[str, str], np.ndarray] = {}
    for cat in CATEGORY_CFG:
        for city in CITY_MULT:
            arr = gen_cat_city_series(cat, city)
            series_map[(cat, city)] = arr
            print(f"  Generated {city} {cat}: mean={arr.mean():.1f}, max={arr.max()}")

    # 为每个 POI 生成日级数据
    poi_daily: dict[str, list[int]] = {}
    for poi in pois:
        cat = poi["category"]
        city = poi["city"]
        series = series_map.get((cat, city))
        if series is None:
            series = series_map.get(("其他", city))
        pop = calc_popularity(poi)
        daily = (series * pop).round().astype(int).tolist()
        poi_daily[poi["id"]] = daily

    print(f"Generated daily data for {len(poi_daily)} POIs")

    # 写入输出
    output = {
        "meta": {
            "year": 2026,
            "start_date": "2026-01-01",
            "days": 365,
            "generated_at": pd.Timestamp.now().isoformat(),
            "categories": list(CATEGORY_CFG.keys()),
            "cities": list(CITY_MULT.keys()),
        },
        "hourly_profiles": HOURLY_PROFILES,
        "poi_daily": poi_daily,
    }

    out_path = Path(__file__).parent.parent / "backend" / "data" / "order_data.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")

    # 统计
    total_orders = sum(sum(v) for v in poi_daily.values())
    avg_daily = total_orders / 365 / len(poi_daily)
    print(f"\nOutput: {out_path}")
    print(f"File size: {out_path.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"Total orders (year): {total_orders:,}")
    print(f"Avg per POI per day: {avg_daily:.1f}")


if __name__ == "__main__":
    main()