"""POI 数据完整性验证脚本。

验证 backend/data/city_poi_db.json 中每条 POI 记录的字段存在性、类型和取值范围。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
BUSINESS_HOURS_RE = re.compile(r"^\d{2}:\d{2}-\d{2}:\d{2}$")


def validate_poi(poi: dict) -> tuple[bool, list[str]]:
    """验证单个 POI 记录。

    Returns:
        (是否有效, 错误信息列表)
    """
    errors: list[str] = []

    # ── 1. 必需字段存在性 ──────────────────────────────────────────
    required_fields = [
        "id",
        "name",
        "city",
        "category",
        "rating",
        "avg_price",
        "lat",
        "lng",
        "business_hours",
        "tags",
        "queue_prone",
        "avg_stay_min",
    ]
    for field in required_fields:
        if field not in poi:
            errors.append(f"缺少必需字段: {field}")

    if errors:
        return False, errors

    # ── 2. 必需字段类型与取值范围 ──────────────────────────────────
    if not isinstance(poi["id"], str) or not poi["id"]:
        errors.append(f"id 必须为非空字符串，当前值: {poi['id']!r}")

    if not isinstance(poi["name"], str) or not poi["name"]:
        errors.append(f"name 必须为非空字符串，当前值: {poi['name']!r}")

    if not isinstance(poi["city"], str) or not poi["city"]:
        errors.append(f"city 必须为非空字符串，当前值: {poi['city']!r}")

    if not isinstance(poi["category"], str) or not poi["category"]:
        errors.append(f"category 必须为非空字符串，当前值: {poi['category']!r}")

    if not isinstance(poi["rating"], (int, float)) or not (0 <= poi["rating"] <= 5):
        errors.append(f"rating 必须在 0-5 之间，当前值: {poi['rating']}")

    if not isinstance(poi["avg_price"], (int, float)) or poi["avg_price"] < 0:
        errors.append(f"avg_price 必须 >= 0，当前值: {poi['avg_price']}")

    if not isinstance(poi["lat"], (int, float)) or not (-90 <= poi["lat"] <= 90):
        errors.append(f"lat 必须在 -90 到 90 之间，当前值: {poi['lat']}")

    if not isinstance(poi["lng"], (int, float)) or not (-180 <= poi["lng"] <= 180):
        errors.append(f"lng 必须在 -180 到 180 之间，当前值: {poi['lng']}")

    if not isinstance(poi["business_hours"], str) or not BUSINESS_HOURS_RE.match(
        poi["business_hours"]
    ):
        errors.append(
            f"business_hours 格式错误，应为 HH:MM-HH:MM，当前值: {poi['business_hours']!r}"
        )

    if not isinstance(poi["tags"], list) or len(poi["tags"]) == 0:
        errors.append("tags 必须是非空列表")

    if not isinstance(poi["avg_stay_min"], int) or poi["avg_stay_min"] <= 0:
        errors.append(f"avg_stay_min 必须是正整数，当前值: {poi['avg_stay_min']}")

    if not isinstance(poi["queue_prone"], bool):
        errors.append(f"queue_prone 必须是布尔值，当前值: {poi['queue_prone']!r}")

    # ── 3. 可选字段验证（存在时检查格式） ─────────────────────────
    if "emotion_tags" in poi:
        _validate_emotion_tags(poi["emotion_tags"], errors)

    if "constraints" in poi:
        _validate_constraints(poi["constraints"], errors)

    return len(errors) == 0, errors


def _validate_emotion_tags(tags: object, errors: list[str]) -> None:
    """验证 emotion_tags 字典。"""
    if not isinstance(tags, dict):
        errors.append(f"emotion_tags 必须是字典，当前类型: {type(tags).__name__}")
        return

    expected_fields = [
        "excitement",
        "tranquility",
        "sociability",
        "culture_depth",
        "surprise",
        "physical_demand",
    ]
    for field in expected_fields:
        if field in tags:
            val = tags[field]
            if not isinstance(val, (int, float)) or not (0 <= val <= 1):
                errors.append(f"emotion_tags.{field} 必须在 0-1 之间，当前值: {val}")


def _validate_constraints(constraints: object, errors: list[str]) -> None:
    """验证 constraints 字典。"""
    if not isinstance(constraints, dict):
        errors.append(f"constraints 必须是字典，当前类型: {type(constraints).__name__}")
        return

    if "queue_time_min" in constraints:
        val = constraints["queue_time_min"]
        if not isinstance(val, int) or val < 0:
            errors.append(f"constraints.queue_time_min 必须 >= 0，当前值: {val}")

    if "accessible" in constraints and not isinstance(constraints["accessible"], bool):
        errors.append(
            f"constraints.accessible 必须是布尔值，当前值: {constraints['accessible']!r}"
        )

    if "pet_friendly" in constraints and not isinstance(
        constraints["pet_friendly"], bool
    ):
        errors.append(
            f"constraints.pet_friendly 必须是布尔值，当前值: {constraints['pet_friendly']!r}"
        )

    if "opening_hours" in constraints and not isinstance(
        constraints["opening_hours"], str
    ):
        errors.append(
            f"constraints.opening_hours 必须是字符串，当前值: {constraints['opening_hours']!r}"
        )

    if "has_restroom" in constraints and not isinstance(
        constraints["has_restroom"], bool
    ):
        errors.append(
            f"constraints.has_restroom 必须是布尔值，当前值: {constraints['has_restroom']!r}"
        )


def validate_all_pois() -> dict[str, object]:
    """验证所有 POI 数据，返回验证结果与统计信息。"""
    data_file = DATA_DIR / "city_poi_db.json"

    if not data_file.exists():
        return {"error": f"数据文件不存在: {data_file}"}

    try:
        pois: list[dict] = json.loads(data_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"error": f"JSON 解析失败: {e}"}

    valid_count = 0
    invalid_pois: list[dict[str, object]] = []
    city_stats: dict[str, int] = {}
    category_stats: dict[str, int] = {}

    for poi in pois:
        is_valid, errors = validate_poi(poi)

        if is_valid:
            valid_count += 1
        else:
            invalid_pois.append({"id": poi.get("id", "unknown"), "errors": errors})

        city = poi.get("city", "unknown")
        city_stats[city] = city_stats.get(city, 0) + 1

        category = poi.get("category", "unknown")
        category_stats[category] = category_stats.get(category, 0) + 1

    return {
        "total": len(pois),
        "valid": valid_count,
        "invalid": len(invalid_pois),
        "invalid_pois": invalid_pois,
        "city_stats": city_stats,
        "category_stats": category_stats,
    }


def main() -> None:
    """命令行入口：运行验证并打印报告。"""
    print("开始验证 POI 数据...")
    result = validate_all_pois()

    if "error" in result:
        print(f"错误: {result['error']}", file=sys.stderr)
        sys.exit(1)

    total = result["total"]
    valid = result["valid"]
    invalid = result["invalid"]
    assert (
        isinstance(total, int) and isinstance(valid, int) and isinstance(invalid, int)
    )

    print("\n验证完成:")
    print(f"  总数: {total}")
    print(f"  有效: {valid}")
    print(f"  无效: {invalid}")

    invalid_pois: list[dict] = result["invalid_pois"]  # type: ignore[assignment]
    if invalid_pois:
        print("\n无效 POI 详情（前 10 条）:")
        for item in invalid_pois[:10]:
            print(f"  {item['id']}: {'; '.join(item['errors'])}")
        if len(invalid_pois) > 10:
            print(f"  ... 还有 {len(invalid_pois) - 10} 个")

    city_stats: dict[str, int] = result["city_stats"]  # type: ignore[assignment]
    print("\n城市分布 (Top 10):")
    for city, count in sorted(city_stats.items(), key=lambda x: -x[1])[:10]:
        print(f"  {city}: {count}")

    category_stats: dict[str, int] = result["category_stats"]  # type: ignore[assignment]
    print("\n类别分布:")
    for category, count in sorted(category_stats.items(), key=lambda x: -x[1]):
        print(f"  {category}: {count}")


if __name__ == "__main__":
    main()
