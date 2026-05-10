"""
CityFlow 数据生成管线

核心流程：
  filter → build_prompt → call_llm → parse → validate → save

每个生成任务（highlights/constraints/experiences/supplement）
都遵循相同的管线模式，通过 BatchGenerator 统一调度。
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from backend.tools.data_generator.models import (
    EMOTION_DIMS,
    GenerationResult,
    HighlightItem,
    NonstandardExperience,
    PoiConstraints,
    PoiHighlights,
    PoiSupplement,
)
from backend.tools.data_generator.providers import LLMProvider, StubProvider


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
POI_DB_PATH = DATA_DIR / "city_poi_db.json"
NSE_PATH = DATA_DIR / "nonstandard_experiences.json"

TARGET_CITIES = ("珠海", "广州")
TARGET_RATING = 4.0

# 生成器按 category 推荐的 highlight type
CATEGORY_HIGHLIGHT_MAP = {
    "文化": ["learn", "view", "photo"],
    "餐饮": ["eat", "rest", "photo"],
    "景点": ["view", "photo", "walk"],
    "运动": ["sport", "play"],
    "购物": ["shop", "eat", "rest"],
}


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def load_json(path: Path) -> list[dict]:
    """安全加载 JSON 文件"""
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: list[dict] | dict) -> None:
    """保存 JSON，自动创建目录"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 已保存: {path}")


def backup_file(path: Path) -> None:
    """备份现有文件（如果存在）"""
    if path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = path.with_suffix(f".{ts}.bak.json")
        shutil.copy2(path, backup)
        print(f"  📦 已备份: {backup.name}")


def filter_high_value_pois(
    pois: list[dict],
    cities: tuple[str, ...] = TARGET_CITIES,
    min_rating: float = TARGET_RATING,
) -> list[dict]:
    """筛选高价值 POI"""
    return [
        p for p in pois
        if p.get("city") in cities and p.get("rating", 0) >= min_rating
    ]


def count_by_city_and_category(pois: list[dict]) -> dict[str, dict[str, int]]:
    """统计各城市各类别 POI 数量"""
    result: dict[str, dict[str, int]] = {}
    for p in pois:
        city = p.get("city", "未知")
        cat = p.get("category", "未知")
        if city not in result:
            result[city] = {}
        result[city][cat] = result[city].get(cat, 0) + 1
    return result


# ──────────────────────────────────────────────
# Prompt 构建器
# ──────────────────────────────────────────────

def build_highlights_prompt(batch: list[dict]) -> str:
    """构建 highlights 生成提示"""
    poi_list = "\n".join(
        f'  - {p["id"]} | {p["name"]} | 类别:{p.get("category")} | 评分:{p.get("rating")} | 城市:{p.get("city")}'
        for p in batch
    )

    category_guide = "\n".join(
        f'  - {cat}: {", ".join(types)}'
        for cat, types in CATEGORY_HIGHLIGHT_MAP.items()
    )

    return f"""你是一个旅游数据生成专家。请为以下 POI 生成 "highlights"（内部体验数据）。

每个 POI 生成 3-6 个 highlight，格式见下方。

# POI 列表（共 {len(batch)} 条）
{poi_list}

# 类别 → 推荐 highlight type
{category_guide}

# highlight type 枚举
- view: 观景（观景台、海景位、夜景）
- photo: 拍照打卡（地标拍照、网红点）
- walk: 散步/漫游（漫步、逛展、溜达）
- eat: 餐饮体验（堂食、品茶、尝小吃）
- shop: 购物（逛街、买手信）
- play: 互动娱乐（DIY体验、游乐设施）
- rest: 休息（歇脚、咖啡、发呆）
- learn: 文化学习（看展、听讲解、阅读）
- sport: 运动（跑步、骑行、爬山）

# emotion_boost 规则
- 键必须是 6 维中的 1-3 个: {", ".join(EMOTION_DIMS)}
- 值范围 0.1-0.5（增量）
- 所有维度值之和不超过 0.8

# 输出格式（严格 JSON 数组）
[
  {{
    "poi_id": "poi_00001",
    "poi_name": "珠海渔女",
    "city": "珠海",
    "category": "文化",
    "highlights": [
      {{
        "id": "hl_poi_00001a",
        "name": "2-10字体验名",
        "type": "view",
        "description": "10-40字描述",
        "duration_min": 20,
        "emotion_boost": {{"tranquility": 0.3, "excitement": 0.1}}
      }}
    ]
  }}
]

注意：
- **必须**包含 poi_id、poi_name、city、category 字段，从上方 POI 列表中获取
- id 格式: hl_{{poi_id}}_{{单字母序号 a/b/c...}}
- **每个 POI 必须有至少 3 个 highlights**，最多 6 个
- name 2-10字，description 10-40字
- duration_min 5-120
- 按 POI 类别选择合适的 highlight type
- 输出只包含 JSON 数组，不要额外说明"""


def build_constraints_prompt(batch: list[dict]) -> str:
    """构建 constraints 生成提示"""
    poi_list = "\n".join(
        f'  - {p["id"]} | {p["name"]} | 类别:{p.get("category")} | {p.get("city")}'
        for p in batch
    )

    return f"""你是一个旅游数据生成专家。请为以下 POI 生成 "constraints"（约束数据）。

# POI 列表（共 {len(batch)} 条）
{poi_list}

# 字段说明
- accessible: 无障碍通行（轮椅/婴儿车）
- pet_friendly: 允许宠物进入
- queue_prone: 是否容易排队
- queue_time_min: 平均排队时间（分钟）
- has_restroom: 有卫生间
- has_parking: 有停车场
- indoor: 室内场所（雨天友好）
- noise_level: "quiet" | "moderate" | "loud"
- best_weather: 从 ["sunny","cloudy","rainy","hot","cold"] 选 1-5 个
- age_groups: 从 ["all","children","adult","elderly"] 选 1-4 个

# 类别参考
- 文化(博物馆/美术馆) → accessible:true, pet_friendly:false, indoor:true, noise_level:quiet
- 文化(露天景点) → accessible:true, pet_friendly:true, indoor:false, noise_level:moderate
- 餐饮(餐厅) → accessible:true, pet_friendly:false, indoor:true, noise_level:moderate
- 餐饮(大排档) → accessible:false, pet_friendly:false, indoor:false, noise_level:loud
- 景点(公园) → accessible:true, pet_friendly:true, indoor:false, noise_level:quiet
- 运动(体育馆) → accessible:true, pet_friendly:false, indoor:true, noise_level:loud
- 购物(商场) → accessible:true, pet_friendly:false, indoor:true, noise_level:moderate

# 输出格式（严格 JSON 数组）
[
  {{
    "poi_id": "poi_00001",
    "poi_name": "POI名称",
    "accessible": true,
    "pet_friendly": false,
    "queue_prone": false,
    "queue_time_min": 0,
    "has_restroom": true,
    "has_parking": false,
    "indoor": false,
    "noise_level": "quiet",
    "best_weather": ["sunny", "cloudy"],
    "age_groups": ["all"]
  }}
]

注意：输出只包含 JSON 数组，不要额外说明"""


def build_experiences_prompt(city: str, count: int, city_guide: str) -> str:
    """构建 nonstandard_experiences 生成提示"""
    city_pinyin_map = {"珠海": "zhuhai", "广州": "guangzhou", "湛江": "zhanjiang", "深圳": "shenzhen"}
    city_pinyin = city_pinyin_map.get(city, city.lower())

    return f"""你是一个旅游数据生成专家。请为 **{city}** 生成 {count} 条 "nonstandard_experiences"（非标体验数据）。

这些体验不是固定 POI，而是时间/情境敏感的体验活动。

# {city} 生成方向参考
{city_guide}

# 字段说明
- id: 格式 "nse_{city_pinyin}_三位数序号"（如 nse_zhuhai_001）
- name: 6-15字中文体验名
- city: "{city}"
- category: 同POI类别体系（文化/餐饮/景点/运动/购物）
- description: 15-50字描述
- best_time: "HH:MM-HH:MM" 格式
- best_time_label: "清晨"|"上午"|"午后"|"傍晚"|"夜晚"
- season: 从 ["spring","summer","autumn","winter"] 选
- emotion_tags: 6维情绪标签（各维 0.0-1.0）
- poi_id: 关联主POI id，纯体验类填 null
- tags: 搜索标签数组
- duration_min: 5-300
- price: 费用（0=免费）

# 最佳时段参考
- 06:00-08:00 → 清晨: 晨跑、日出、早市
- 08:00-11:00 → 上午: 博物馆、文化体验、早茶
- 11:00-14:00 → 午后: 午餐、室内活动
- 14:00-17:00 → 午后: 下午茶、购物、展览
- 17:00-19:00 → 傍晚: 日落、散步、晚餐
- 19:00-22:00 → 夜晚: 夜景、夜市、酒吧

# 输出格式（严格 JSON 数组）
[
  {{
    "id": "nse_{city_pinyin}_001",
    "name": "情侣路晨跑",
    "city": "{city}",
    "category": "运动",
    "description": "沿着情侣路晨跑，看日出海景，感受海滨城市的苏醒",
    "best_time": "06:00-08:00",
    "best_time_label": "清晨",
    "season": ["spring", "summer", "autumn"],
    "emotion_tags": {{
      "excitement": 0.7, "tranquility": 0.3, "sociability": 0.1,
      "culture_depth": 0.1, "surprise": 0.4, "physical_demand": 0.8
    }},
    "poi_id": null,
    "tags": ["晨跑", "海边", "日出", "免费"],
    "duration_min": 60,
    "price": 0
  }}
]

注意：输出只包含 JSON 数组，不要额外说明"""


def build_supplement_prompt(city: str, category: str, count: int) -> str:
    """构建 POI 补充提示"""
    culture_tips = "- emotion_tags 中 culture_depth 应偏高（0.7-1.0）\n- physical_demand 偏低（0.1-0.3）"
    sport_tips = "- emotion_tags 中 physical_demand 应偏高（0.6-1.0）\n- excitement 中高（0.5-0.8）"

    tips = culture_tips if category == "文化" else sport_tips
    examples = "博物馆、美术馆、纪念馆、图书馆、文化馆、历史建筑" if category == "文化" else "公园、体育馆、健身中心、游泳馆、登山步道、骑行道"

    city_pinyin_map = {"珠海": "zhuhai", "广州": "guangzhou", "湛江": "zhanjiang", "深圳": "shenzhen"}
    city_pinyin = city_pinyin_map.get(city, city.lower())

    return f"""你是一个旅游数据生成专家。请为 **{city}** 生成 {count} 条 **{category}** 类 POI。

# 格式
完全沿用 city_poi_db.json 的现有格式。

# {category} 类生成提示
{tips}

# 类型举例
{examples}

# 输出格式（严格 JSON 数组）
[
  {{
    "id": "poi_{category}_{city_pinyin}_001",
    "name": "POI名称（2-30字）",
    "city": "{city}",
    "category": "{category}",
    "rating": 4.0-5.0,
    "avg_price": 0-200,
    "lat": 22.0-23.5（珠海）或 23.0-23.5（广州）,
    "lng": 113.0-114.0,
    "business_hours": "09:00-17:00",
    "tags": ["免费", "涨知识", "室内"],
    "queue_prone": false,
    "avg_stay_min": 60-180,
    "emotion_tags": {{
      "excitement": 0.3, "tranquility": 0.6, "sociability": 0.2,
      "culture_depth": 0.9, "surprise": 0.4, "physical_demand": 0.1
    }}
  }}
]

注意：
- id 格式: poi_{category}_{city_pinyin}_{三位数序号}
- lat/lng 需在对应城市的合理范围
- 输出只包含 JSON 数组，不要额外说明"""


# ──────────────────────────────────────────────
# 解析器
# ──────────────────────────────────────────────

def parse_llm_array(raw: str) -> list[dict]:
    """将 LLM 返回的文本解析为 list[dict]"""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.removeprefix("```json").removeprefix("```")
        raw = raw.removesuffix("```").strip()
    return json.loads(raw)


# ──────────────────────────────────────────────
# 批处理器
# ──────────────────────────────────────────────

@dataclass
class BatchGenerator:
    """
    通用批量生成器

    流程：
      1. 将输入分批（batch_size 条一组）
      2. 每批调用 LLM
      3. 解析并校验结果
      4. 写入输出文件
    """

    provider: LLMProvider
    prompt_builder: Callable[[list[dict]], str]
    model_class: type  # Pydantic model class
    output_name: str  # 输出文件名（如 "poi_highlights.json"）
    batch_size: int = 10  # 每批处理多少条 POI
    delay_seconds: float = 1.0  # 批次间延迟（避免限流）

    def run(
        self,
        items: list[dict],
        item_key: str = "poi_id",
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> GenerationResult:
        """执行批量生成"""
        output_path = DATA_DIR / self.output_name
        total = len(items)
        all_results: list[dict] = []
        errors: list[str] = []

        backup_file(output_path)

        for i in range(0, total, self.batch_size):
            batch = items[i : i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (total + self.batch_size - 1) // self.batch_size

            print(f"\n  📝 批次 {batch_num}/{total_batches} ({len(batch)} 条)")

            try:
                prompt = self.prompt_builder(batch)
                raw = self.provider.generate(prompt)
                parsed = self.provider.parse_response(raw)

                # LLM 返回的可能是 { "data": [...] } 或 [...]
                if isinstance(parsed, dict) and "data" in parsed:
                    parsed = parsed["data"]

                # 校验并累加
                validated = self._validate_batch(parsed, batch)
                all_results.extend(validated)

                if progress_callback:
                    progress_callback(min(i + self.batch_size, total), total)

            except Exception as e:
                err_msg = f"批次 {batch_num} 失败: {e}"
                print(f"  ❌ {err_msg}")
                errors.append(err_msg)

            # 批次间延迟
            if i + self.batch_size < total:
                time.sleep(self.delay_seconds)

        # 保存结果
        if all_results:
            save_json(output_path, all_results)

        return GenerationResult(
            task_name=self.output_name,
            success_count=len(all_results),
            fail_count=len(errors),
            errors=errors,
            output_path=str(output_path),
        )

    def _validate_batch(self, parsed: Any, batch: list[dict]) -> list[dict]:
        """校验 LLM 输出的每一条数据"""
        if not isinstance(parsed, list):
            raise ValueError(f"LLM 返回的不是数组，而是 {type(parsed).__name__}")

        validated = []
        for item in parsed:
            try:
                obj = self.model_class(**item)
                validated.append(obj.model_dump())
            except Exception as e:
                print(f"    ⚠️ 校验失败 (poi={item.get('poi_id', '?')}): {e}")
                continue
        return validated


# ──────────────────────────────────────────────
# 整体管线调度
# ──────────────────────────────────────────────

class DataPipeline:
    """
    数据生成管线调度器
    管理 4 个生成任务的执行顺序和依赖。
    """

    def __init__(self, provider: LLMProvider | None = None):
        self.provider = provider or StubProvider()
        self.pois = load_json(POI_DB_PATH)
        self.high_value_pois = filter_high_value_pois(self.pois)

    def run_highlights(self) -> GenerationResult:
        """生成 POI highlights"""
        print(f"\n{'='*60}")
        print(f"📌 任务 1: POI highlights")
        print(f"   目标: {len(self.high_value_pois)} 条 POI")
        print(f"   输出: poi_highlights.json")
        print(f"{'='*60}")

        generator = BatchGenerator(
            provider=self.provider,
            prompt_builder=build_highlights_prompt,
            model_class=PoiHighlights,
            output_name="poi_highlights.json",
            batch_size=20,       # 全量模式：每批20条POI
            delay_seconds=0.5,   # 批次间短延迟
        )
        return generator.run(self.high_value_pois)

    def run_constraints(self) -> GenerationResult:
        """生成 POI constraints"""
        print(f"\n{'='*60}")
        print(f"📌 任务 2: POI constraints")
        print(f"   目标: {len(self.high_value_pois)} 条 POI")
        print(f"   输出: poi_constraints.json")
        print(f"{'='*60}")

        generator = BatchGenerator(
            provider=self.provider,
            prompt_builder=build_constraints_prompt,
            model_class=PoiConstraints,
            output_name="poi_constraints.json",
            batch_size=50,       # 全量模式：每批50条POI
            delay_seconds=0.5,
        )
        return generator.run(self.high_value_pois)

    def run_experiences(self) -> GenerationResult:
        """扩充 nonstandard_experiences"""
        print(f"\n{'='*60}")
        print(f"📌 任务 3: nonstandard_experiences 扩充")
        print(f"   输出: nonstandard_experiences.json")
        print(f"{'='*60}")

        # 各城市生成配置
        city_configs = {
            "珠海": {"count": 40, "guide": (
                "- 海滨活动: 情侣路晨跑、海滨泳场、日出观景、渔女打卡\n"
                "- 海岛体验: 环岛骑行、海岛露营、赶海拾贝\n"
                "- 城市漫步: 老香洲街巷漫游、唐家湾古镇、北山会馆\n"
                "- 美食体验: 早茶叹茶、海鲜市场、夜市小吃\n"
                "- 夜生活: 情侣路夜骑、日月贝夜景、酒吧街"
            )},
            "广州": {"count": 45, "guide": (
                "- 老城体验: 荔湾湖晨运、恩宁路骑楼漫步、西关大屋探访\n"
                "- 美食: 凌晨茶楼叹早茶、沙面下午茶、夜市觅食\n"
                "- 文化: 陈家祠参观、粤剧体验、东山口看展\n"
                "- 自然: 白云山晨爬、越秀公园散步、珠江夜游\n"
                "- 现代: 珠江新城CBD漫步、K11看展、琶醍夜市"
            )},
            "湛江": {"count": 25, "guide": (
                "- 渔港: 渔港日落、海鲜市场、码头漫步\n"
                "- 海岛: 特呈岛骑行、硇洲岛探险\n"
                "- 美食: 炭烤生蚝、湛江鸡、夜市大排档"
            )},
            "深圳": {"count": 35, "guide": (
                "- 科技: 科技园探访、无人机体验、AI互动展\n"
                "- 海滨: 深圳湾日出、盐田栈道、大小梅沙\n"
                "- 城市: 华强北扫街、华侨城创意园、海上世界"
            )},
        }

        all_results: list[dict] = []
        errors: list[str] = []

        output_path = DATA_DIR / "nonstandard_experiences.json"
        backup_file(output_path)

        for city, cfg in city_configs.items():
            print(f"\n  🏙️ 生成 {city} ({cfg['count']} 条)...")
            prompt = build_experiences_prompt(city, cfg["count"], cfg["guide"])

            try:
                raw = self.provider.generate(prompt)
                parsed = self.provider.parse_response(raw)
                if isinstance(parsed, dict) and "data" in parsed:
                    parsed = parsed["data"]

                for item in parsed:
                    try:
                        obj = NonstandardExperience(**item)
                        all_results.append(obj.model_dump())
                    except Exception as e:
                        print(f"    ⚠️ 校验失败: {e}")
                        errors.append(f"{item.get('id', '?')}: {e}")

                print(f"    ✅ 成功 {sum(1 for _ in parsed)} 条")

            except Exception as e:
                print(f"    ❌ 失败: {e}")
                errors.append(f"{city}: {e}")

            time.sleep(1.0)

        if all_results:
            save_json(output_path, all_results)

        return GenerationResult(
            task_name="nonstandard_experiences",
            success_count=len(all_results),
            fail_count=len(errors),
            errors=errors,
            output_path=str(output_path),
        )

    def run_supplement(self) -> GenerationResult:
        """生成 POI 补充（文化/运动）"""
        print(f"\n{'='*60}")
        print(f"📌 任务 4: POI 类别平衡补充")
        print(f"   输出: poi_supplement.json")
        print(f"{'='*60}")

        # 统计现有各类别数量
        stats = count_by_city_and_category(self.pois)
        print(f"\n  当前各城市文化/运动数量:")
        for city in ("珠海", "广州"):
            cats = stats.get(city, {})
            print(f"    {city}: 文化={cats.get('文化', 0)}, 运动={cats.get('运动', 0)}")

        # 需要补充的数量
        supplement_targets = [
            ("珠海", "文化", 70),   # ~50 → 120+
            ("珠海", "运动", 35),   # ~15 → 50+
            ("广州", "文化", 70),   # ~80 → 150+
            ("广州", "运动", 40),   # ~20 → 60+
        ]

        all_results: list[dict] = []
        errors: list[str] = []

        output_path = DATA_DIR / "poi_supplement.json"
        backup_file(output_path)

        for city, category, count in supplement_targets:
            print(f"\n  🏙️ 补充 {city} {category} ({count} 条)...")
            prompt = build_supplement_prompt(city, category, count)

            try:
                raw = self.provider.generate(prompt)
                parsed = self.provider.parse_response(raw)
                if isinstance(parsed, dict) and "data" in parsed:
                    parsed = parsed["data"]

                for item in parsed:
                    try:
                        obj = PoiSupplement(**item)
                        all_results.append(obj.model_dump())
                    except Exception as e:
                        print(f"    ⚠️ 校验失败: {e}")
                        errors.append(f"{item.get('id', '?')}: {e}")

                print(f"    ✅ 成功 {sum(1 for _ in parsed)} 条")

            except Exception as e:
                print(f"    ❌ 失败: {e}")
                errors.append(f"{city}/{category}: {e}")

            time.sleep(1.0)

        if all_results:
            save_json(output_path, all_results)

        return GenerationResult(
            task_name="poi_supplement",
            success_count=len(all_results),
            fail_count=len(errors),
            errors=errors,
            output_path=str(output_path),
        )

    def run_dry_run(self) -> None:
        """干跑：不调用 LLM，只输出各任务的统计信息和示例提示"""
        print(f"\n{'='*60}")
        print(f"🔍 干跑模式 - 统计信息")
        print(f"{'='*60}")

        print(f"\n📊 POI 数据总览")
        print(f"  总数: {len(self.pois)}")
        stats = count_by_city_and_category(self.pois)
        for city, cats in stats.items():
            print(f"  {city}:")
            for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
                print(f"    {cat}: {n}")

        print(f"\n📊 高价值 POI（{TARGET_CITIES} & rating>={TARGET_RATING}）")
        print(f"  数量: {len(self.high_value_pois)}")
        hv_stats = count_by_city_and_category(self.high_value_pois)
        for city, cats in hv_stats.items():
            for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
                print(f"    {city} / {cat}: {n}")

        print(f"\n📝 示例 Prompt（highlights，前 3 条 POI）")
        sample_prompt = build_highlights_prompt(self.high_value_pois[:3])
        print(sample_prompt[:500] + "\n...（省略）")

        print(f"\n📝 示例 Prompt（experiences - 珠海）")
        sample_exp = build_experiences_prompt(
            "珠海", 3,
            "- 海滨活动: 情侣路晨跑\n- 海岛体验: 环岛骑行"
        )
        print(sample_exp[:500] + "\n...（省略）")

        print(f"\n📦 输出文件:")
        print(f"  {DATA_DIR / 'poi_highlights.json'}")
        print(f"  {DATA_DIR / 'poi_constraints.json'}")
        print(f"  {DATA_DIR / 'nonstandard_experiences.json'}")
        print(f"  {DATA_DIR / 'poi_supplement.json'}")
