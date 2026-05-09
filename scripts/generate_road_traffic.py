"""
生成 2026 年珠海/广州/湛江道路拥堵指数（TTI）模拟数据
TTI = (1.0 + 2.0 * hour_factor) × weekday_mult × holiday_mult × seasonal
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np

# ============== 路段定义 ==============

ROADS = [
    # 珠海
    {"road_id": "rd_zh_01", "name": "情侣路", "city": "珠海", "road_type": "主干道", "lng": 113.55, "lat": 22.27},
    {"road_id": "rd_zh_02", "name": "迎宾南路", "city": "珠海", "road_type": "主干道", "lng": 113.53, "lat": 22.27},
    {"road_id": "rd_zh_03", "name": "九洲大道", "city": "珠海", "road_type": "主干道", "lng": 113.52, "lat": 22.25},
    {"road_id": "rd_zh_04", "name": "珠海大道", "city": "珠海", "road_type": "主干道", "lng": 113.48, "lat": 22.23},
    {"road_id": "rd_zh_05", "name": "明珠路", "city": "珠海", "road_type": "次干道", "lng": 113.51, "lat": 22.24},
    {"road_id": "rd_zh_06", "name": "金凤路", "city": "珠海", "road_type": "高速", "lng": 113.50, "lat": 22.30},
    {"road_id": "rd_zh_07", "name": "凤凰路", "city": "珠海", "road_type": "次干道", "lng": 113.54, "lat": 22.28},
    {"road_id": "rd_zh_08", "name": "人民路", "city": "珠海", "road_type": "主干道", "lng": 113.53, "lat": 22.28},
    {"road_id": "rd_zh_09", "name": "柠溪路", "city": "珠海", "road_type": "次干道", "lng": 113.56, "lat": 22.27},
    {"road_id": "rd_zh_10", "name": "梅华路", "city": "珠海", "road_type": "次干道", "lng": 113.55, "lat": 22.28},
    # 广州
    {"road_id": "rd_gz_01", "name": "天河路", "city": "广州", "road_type": "主干道", "lng": 113.36, "lat": 23.13},
    {"road_id": "rd_gz_02", "name": "中山路", "city": "广州", "road_type": "主干道", "lng": 113.26, "lat": 23.13},
    {"road_id": "rd_gz_03", "name": "东风路", "city": "广州", "road_type": "主干道", "lng": 113.27, "lat": 23.13},
    {"road_id": "rd_gz_04", "name": "环市路", "city": "广州", "road_type": "主干道", "lng": 113.28, "lat": 23.13},
    {"road_id": "rd_gz_05", "name": "黄埔大道", "city": "广州", "road_type": "主干道", "lng": 113.40, "lat": 23.12},
    {"road_id": "rd_gz_06", "name": "广州大道", "city": "广州", "road_type": "主干道", "lng": 113.32, "lat": 23.12},
    {"road_id": "rd_gz_07", "name": "华南快速", "city": "广州", "road_type": "高速", "lng": 113.40, "lat": 23.18},
    {"road_id": "rd_gz_08", "name": "内环路", "city": "广州", "road_type": "主干道", "lng": 113.27, "lat": 23.13},
    {"road_id": "rd_gz_09", "name": "新光快速", "city": "广州", "road_type": "高速", "lng": 113.35, "lat": 23.18},
    {"road_id": "rd_gz_10", "name": "机场高速", "city": "广州", "road_type": "高速", "lng": 113.30, "lat": 23.22},
    # 湛江
    {"road_id": "rd_zj_01", "name": "人民大道", "city": "湛江", "road_type": "主干道", "lng": 110.40, "lat": 21.20},
    {"road_id": "rd_zj_02", "name": "解放路", "city": "湛江", "road_type": "主干道", "lng": 110.36, "lat": 21.20},
    {"road_id": "rd_zj_03", "name": "海滨大道", "city": "湛江", "road_type": "主干道", "lng": 110.41, "lat": 21.19},
    {"road_id": "rd_zj_04", "name": "椹川大道", "city": "湛江", "road_type": "主干道", "lng": 110.36, "lat": 21.25},
    {"road_id": "rd_zj_05", "name": "疏港大道", "city": "湛江", "road_type": "高速", "lng": 110.38, "lat": 21.28},
    {"road_id": "rd_zj_06", "name": "乐山路", "city": "湛江", "road_type": "次干道", "lng": 110.40, "lat": 21.22},
]

# ============== 时间因子 ==============

# 2026 年节假日 {date: (高速倍率, 城区倍率)}
HOLIDAYS = {
    date(2026, 1, 1): (1.2, 0.9), date(2026, 1, 2): (1.2, 0.9), date(2026, 1, 3): (1.1, 0.9),
    date(2026, 2, 17): (1.3, 0.7), date(2026, 2, 18): (1.3, 0.7), date(2026, 2, 19): (1.2, 0.8),
    date(2026, 2, 20): (1.1, 0.9), date(2026, 2, 21): (1.1, 1.0), date(2026, 2, 22): (1.0, 1.1), date(2026, 2, 23): (1.0, 1.2),
    date(2026, 4, 4): (1.1, 1.1), date(2026, 4, 5): (1.2, 1.0), date(2026, 4, 6): (1.1, 0.9),
    date(2026, 5, 1): (1.3, 1.0), date(2026, 5, 2): (1.3, 1.1), date(2026, 5, 3): (1.2, 1.1),
    date(2026, 5, 4): (1.2, 1.0), date(2026, 5, 5): (1.1, 0.9),
    date(2026, 6, 19): (1.1, 1.1), date(2026, 6, 20): (1.2, 1.0), date(2026, 6, 21): (1.1, 0.9),
    date(2026, 10, 1): (1.3, 0.7), date(2026, 10, 2): (1.3, 0.7), date(2026, 10, 3): (1.2, 0.8),
    date(2026, 10, 4): (1.1, 0.9), date(2026, 10, 5): (1.1, 1.0), date(2026, 10, 6): (1.0, 1.1),
    date(2026, 10, 7): (1.0, 1.1), date(2026, 10, 8): (1.0, 1.0),
}

# 工作日小时因子 (index = hour)
HF_WORKDAY = [0.05, 0.03, 0.02, 0.02, 0.03, 0.10, 0.35, 0.70,
               1.00, 0.75, 0.55, 0.50, 0.55, 0.50, 0.45, 0.50,
               0.65, 0.90, 1.00, 0.70, 0.40, 0.25, 0.15, 0.08]
# 周末小时因子
HF_WEEKEND = [0.05, 0.03, 0.02, 0.02, 0.03, 0.05, 0.10, 0.25,
               0.45, 0.60, 0.70, 0.75, 0.70, 0.65, 0.60, 0.60,
               0.55, 0.55, 0.50, 0.40, 0.30, 0.20, 0.12, 0.08]

# 星期因子 (Mon=0, ..., Sun=6)
WD_MULT = {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.10, 5: 0.70, 6: 0.65}

START_DATE = date(2026, 1, 1)
END_DATE = date(2026, 12, 31)


def holiday_mult(d: date, road_type: str) -> float:
    h = HOLIDAYS.get(d, (1.0, 1.0))
    return h[0] if road_type == "高速" else h[1]


def seasonal_factor(d: date) -> float:
    day_of_year = (d - START_DATE).days
    return 1.0 + 0.08 * np.sin(2 * np.pi * day_of_year / 365)


def compute_tti(hf: float, wd: float, hd: float, sc: float, noise: float) -> float:
    """hour_factor × weekday × holiday × seasonal → TTI"""
    # TTI = (1 + 1.3*hf) × wd × hd × sc
    # hf=1.0(早高峰) → base=2.3; hf=0.5(平峰) → base=1.65; hf=0.1(深夜) → base=1.13
    tti = (1.0 + 1.3 * hf) * wd * hd * sc
    # 加 ±noise% 噪声
    tti *= (1.0 + noise)
    return max(1.0, round(tti, 3))


def tti_level(tti: float) -> str:
    if tti < 1.2: return "畅通"
    if tti < 1.5: return "缓行"
    if tti < 2.0: return "拥堵"
    return "严重拥堵"


def gen_road_series(road: dict) -> list:
    rng = np.random.default_rng(hash(road["road_id"]) & 0xFFFFFFFF)
    dates = [START_DATE + timedelta(days=i) for i in range(365)]
    hourly_tti = []

    for d in dates:
        wd = WD_MULT[d.weekday()]
        hd = holiday_mult(d, road["road_type"])
        sc = seasonal_factor(d)
        hfs = HF_WEEKEND if d.weekday() >= 5 else HF_WORKDAY

        day_tti = []
        for h in range(24):
            hf = hfs[h]
            # TTI = (1.3 + hf) × weekday × holiday × seasonal + 随机噪声 ±2%
            n = rng.normal(0, 0.02)
            tti = (1.3 + hf) * wd * hd * sc * (1.0 + n)
            day_tti.append(round(max(1.0, tti), 3))
        hourly_tti.append(day_tti)

    return hourly_tti


def main():
    print(f"Generating road traffic data for {len(ROADS)} roads...")

    hourly_congestion = {}
    for road in ROADS:
        series = gen_road_series(road)
        hourly_congestion[road["road_id"]] = series
        # 周一早高峰 8:00 (index 3 = Jan 4, index 8 = 8am)
        tti_am = series[3][8]
        print(f"  {road['city']} {road['name']}: TTI Mon-8am={tti_am} ({tti_level(tti_am)})")

    # 春节 vs 平日对比
    sf_day = 47  # Feb 17
    sf_tti = hourly_congestion["rd_zh_01"][sf_day][19]  # 春节晚高峰
    normal_tti = hourly_congestion["rd_zh_01"][3][19]     # 平日晚高峰
    print(f"\n  珠海情侣路 春节 19:00 TTI={sf_tti} ({tti_level(sf_tti)}) vs 平日 19:00 TTI={normal_tti} ({tti_level(normal_tti)})")

    # 平日早高峰 vs 深夜
    rush = hourly_congestion["rd_gz_01"][3][8]
    night = hourly_congestion["rd_gz_01"][3][2]
    print(f"  广州天河路 周一 8:00 TTI={rush} ({tti_level(rush)}) vs 3:00 TTI={night} ({tti_level(night)})")

    output = {
        "meta": {
            "year": 2026, "start_date": "2026-01-01", "days": 365,
            "formula": "TTI = (1 + 2*hf) * wd * hd * sc, noise ±3%",
            "cities": list({r["city"] for r in ROADS}),
        },
        "roads": ROADS,
        "hourly_congestion": hourly_congestion,
    }

    out_path = Path(__file__).parent.parent / "backend" / "data" / "road_traffic_data.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    print(f"\nOutput: {out_path} ({out_path.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
