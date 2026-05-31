"""Append ~50 new food POIs to city_poi_db.json to fill coverage gaps.

Coverage gaps:
  1. Vegetarian (6)
  2. Romantic restaurants (6)
  3. Doumen/Jinwan food (12)
  4. Farmhouse/nongjiale (8)
  5. Morning tea / Cantonese (6)
  6. Desserts / cold drinks (8)
  7. Hengqin specialties (6)

Total: 52 new POIs, IDs from poi_04736 onward.
"""

import json
import random
from pathlib import Path

DATA_FILE = Path(r"C:\Users\wang\Desktop\hks美团\backend\data\city_poi_db.json")


def _rand_rating() -> float:
    return round(random.uniform(3.5, 4.8), 1)


def _rand_comments(tags: list[str]) -> list[dict]:
    """Generate 2 realistic UGC comments based on tags."""
    users = ["小鱼", "阿杰", "琳琳", "大雄", "晓晴", "老陈", "小雅", "阿明", "甜甜", "志远"]
    positive = [
        "味道很赞，食材新鲜，下次还来。",
        "环境不错，服务态度好，分量足。",
        "朋友推荐的，果然没失望，值得打卡。",
        "性价比很高，适合多人聚餐。",
        "口味正宗，喜欢这种家常味道。",
        "装修有特色，菜品种类多，挑不出来毛病。",
        "排队等了一会儿但是值得，出品稳定。",
        "意外的惊喜，宝藏小店！",
        "带着家人来的，大家都说好吃。",
        "周末来的，人不少但上菜快。",
    ]
    return [
        {"user": random.choice(users), "rating": random.randint(3, 5), "content": random.choice(positive)}
        for _ in range(2)
    ]


def _emotion_tags(excitement: float, tranquility: float, culture: float = 0.2) -> dict:
    return {
        "excitement": round(excitement, 2),
        "tranquility": round(tranquility, 2),
        "sociability": round(random.uniform(0.4, 0.8), 2),
        "culture_depth": round(culture, 2),
        "surprise": round(random.uniform(0.2, 0.5), 2),
        "physical_demand": round(random.uniform(0.1, 0.25), 2),
    }


def _suitability(couples: bool = True, family: bool = True, solo: bool = False, friends: bool = True) -> dict:
    return {
        "情侣友好": couples,
        "亲子友好": family,
        "独自友好": solo,
        "朋友友好": friends,
    }


def _constraints(pet_friendly: bool = False, queue_min: int = 5, hours: str = "10:00-22:00") -> dict:
    return {
        "accessible": True,
        "pet_friendly": pet_friendly,
        "queue_time_min": queue_min,
        "opening_hours": hours,
    }


def _base_poi(
    idx: int,
    name: str,
    lat: float,
    lng: float,
    avg_price: int,
    display_cat: str,
    tags: list[str],
    scene_tags: list[str],
    hours: str = "10:00-22:00",
    stay_min: int = 45,
    queue_prone: bool = False,
    pet_friendly: bool = False,
    queue_min: int = 5,
    couples: bool = True,
    family: bool = True,
    solo: bool = False,
    friends: bool = True,
    excitement: float = 0.4,
    tranquility: float = 0.4,
    culture: float = 0.2,
    score: int = 7,
) -> dict:
    return {
        "id": f"poi_{idx:05d}",
        "name": name,
        "city": "珠海",
        "category": "餐饮",
        "rating": _rand_rating(),
        "avg_price": avg_price,
        "lat": round(lat + random.uniform(-0.005, 0.005), 7),
        "lng": round(lng + random.uniform(-0.005, 0.005), 7),
        "business_hours": hours,
        "tags": tags,
        "queue_prone": queue_prone,
        "avg_stay_min": stay_min,
        "ugc_comments": _rand_comments(tags),
        "emotion_tags": _emotion_tags(excitement, tranquility, culture),
        "_scene_tags": scene_tags,
        "_suitability": _suitability(couples, family, solo, friends),
        "_llm_quality": {"is_tourist": False, "score": score, "issues": []},
        "constraints": _constraints(pet_friendly=pet_friendly, queue_min=queue_min, hours=hours),
        "_display_category": display_cat,
    }


# ---------------------------------------------------------------------------
# Category 1: Vegetarian (6)
# ---------------------------------------------------------------------------
def vegetarian() -> list[dict]:
    data = [
        ("素心素食馆", 22.273, 113.575, 55, ["素食", "健康", "自助"], ["美食", "素食健康"]),
        ("一叶菩提素食餐厅", 22.232, 113.553, 68, ["素食", "禅意", "环境好"], ["美食", "素食健康", "拍照出片"]),
        ("清心素食自助", 22.235, 113.552, 42, ["素食", "自助", "平价"], ["美食", "素食健康"]),
        ("绿野仙踪素食坊", 22.252, 113.572, 60, ["素食", "创意菜", "有机"], ["美食", "素食健康"]),
        ("莲花素食馆", 22.363, 113.583, 48, ["素食", "家常", "安静"], ["美食", "素食健康"]),
        ("慈心素食", 22.271, 113.568, 52, ["素食", "佛系", "养生"], ["美食", "素食健康"]),
    ]
    return [
        _base_poi(
            idx, name, lat, lng, price, "正餐", tags, scene,
            hours="09:00-21:30", stay_min=40, excitement=0.3, tranquility=0.7, culture=0.4, score=6,
        )
        for idx, (name, lat, lng, price, tags, scene) in enumerate(data, start=4736)
    ]


# ---------------------------------------------------------------------------
# Category 2: Romantic restaurants (6)
# ---------------------------------------------------------------------------
def romantic() -> list[dict]:
    data = [
        ("海景西餐厅", 22.251, 113.573, 220, ["浪漫", "约会", "海景", "西餐"], ["美食", "浪漫约会", "海景"]),
        ("月光法餐厅", 22.233, 113.571, 280, ["浪漫", "约会", "法餐", "烛光晚餐"], ["美食", "浪漫约会"]),
        ("蓝湾扒房", 22.221, 113.553, 260, ["浪漫", "牛排", "红酒", "约会"], ["美食", "浪漫约会"]),
        ("星海水岸餐厅", 22.244, 113.534, 200, ["浪漫", "海景", "创意菜", "约会"], ["美食", "浪漫约会", "海景"]),
        ("花间集融合菜", 22.253, 113.575, 180, ["浪漫", "融合菜", "环境好", "约会"], ["美食", "浪漫约会", "拍照出片"]),
        ("天鹅湖畔餐厅", 22.224, 113.549, 300, ["浪漫", "西餐", "湖景", "纪念日"], ["美食", "浪漫约会"]),
    ]
    return [
        _base_poi(
            idx, name, lat, lng, price, "正餐", tags, scene,
            hours="11:00-23:00", stay_min=80, queue_prone=True, queue_min=15,
            couples=True, family=False, solo=False, friends=False,
            excitement=0.6, tranquility=0.6, culture=0.3, score=7,
        )
        for idx, (name, lat, lng, price, tags, scene) in enumerate(data, start=4742)
    ]


# ---------------------------------------------------------------------------
# Category 3: Doumen / Jinwan food (12)
# ---------------------------------------------------------------------------
def doumen_jinwan() -> list[dict]:
    data = [
        # Doumen town area
        ("斗门老街烧腊店", 22.222, 113.282, 35, ["烧腊", "老字号", "本地特色"], ["美食", "本地老店"], "地方小吃", 30),
        ("斗门客家王", 22.218, 113.285, 55, ["客家菜", "本地特色", "实惠"], ["美食", "本地老店"], "正餐", 50),
        ("赵氏濑粉", 22.205, 113.303, 18, ["濑粉", "早餐", "本地特色"], ["美食", "本地老店"], "地方小吃", 20),
        ("井岸煲仔饭", 22.208, 113.298, 28, ["煲仔饭", "本地特色", "锅巴"], ["美食", "本地老店"], "地方小吃", 25),
        # Jinwan / airport area
        ("金湾海鲜大排档", 22.118, 113.353, 85, ["海鲜", "大排档", "现捞现做"], ["美食", "海鲜大排档"], "正餐", 60),
        ("红旗烧鹅大王", 22.123, 113.348, 45, ["烧鹅", "烧腊", "本地特色"], ["美食", "本地老店"], "正餐", 35),
        ("三灶田园海鲜", 22.083, 113.383, 75, ["海鲜", "农家", "新鲜"], ["美食", "海鲜大排档"], "正餐", 55),
        ("金湾渔港大排档", 22.055, 113.382, 90, ["海鲜", "大排档", "渔民直供"], ["美食", "海鲜大排档"], "正餐", 60),
        # More Doumen
        ("斗门粥城", 22.215, 113.278, 25, ["粥", "夜宵", "本地特色"], ["美食", "夜宵"], "地方小吃", 30),
        ("乾务糖水铺", 22.235, 113.265, 15, ["糖水", "甜品", "传统"], ["美食", "甜品消暑"], "甜品饮品", 20),
        ("井岸大包店", 22.210, 113.300, 12, ["包子", "早餐", "本地特色"], ["美食", "本地老店"], "地方小吃", 15),
        ("三灶咸茶馆", 22.080, 113.378, 20, ["咸茶", "本地特色", "传统"], ["美食", "本地老店"], "地方小吃", 25),
    ]
    pois = []
    for i, (name, lat, lng, price, tags, scene, dcat, stay) in enumerate(data, start=4748):
        pois.append(_base_poi(
            i, name, lat, lng, price, dcat, tags, scene,
            hours="07:00-22:00" if "早餐" in tags else "10:00-22:00",
            stay_min=stay, excitement=0.35, tranquility=0.4, culture=0.5, score=6,
        ))
    return pois


# ---------------------------------------------------------------------------
# Category 4: Farmhouse / nongjiale (8)
# ---------------------------------------------------------------------------
def farmhouse() -> list[dict]:
    data = [
        ("莲江农家菜馆", 22.242, 113.272, 70, ["农家菜", "土鸡", "田园"], ["美食", "农家乐"]),
        ("斗门田园农庄", 22.225, 113.278, 65, ["农家菜", "采摘", "土猪肉"], ["美食", "农家乐"]),
        ("金鼎果园农庄", 22.372, 113.563, 80, ["农家菜", "采摘", "荔枝"], ["美食", "农家乐"]),
        ("十里莲江农庄", 22.248, 113.268, 75, ["农家菜", "莲藕", "田园"], ["美食", "农家乐"]),
        ("三灶渔家乐", 22.085, 113.373, 60, ["农家菜", "海鲜", "渔家"], ["美食", "农家乐", "海鲜大排档"]),
        ("斗门荔枝园农庄", 22.232, 113.275, 85, ["农家菜", "荔枝", "采摘"], ["美食", "农家乐"]),
        ("金鼎柴火鸡", 22.375, 113.558, 55, ["农家菜", "柴火鸡", "土灶"], ["美食", "农家乐"]),
        ("红旗田园农家乐", 22.128, 113.343, 50, ["农家菜", "土鸡", "池塘钓鱼"], ["美食", "农家乐"]),
    ]
    return [
        _base_poi(
            idx, name, lat, lng, price, "正餐", tags, scene,
            hours="09:00-21:00", stay_min=70, pet_friendly=(i % 3 == 0),
            couples=False, family=True, solo=False, friends=True,
            excitement=0.35, tranquility=0.6, culture=0.3, score=6,
        )
        for i, (idx, (name, lat, lng, price, tags, scene)) in enumerate(enumerate(data, start=4760))
    ]


# ---------------------------------------------------------------------------
# Category 5: Morning tea / Cantonese (6)
# ---------------------------------------------------------------------------
def morning_tea() -> list[dict]:
    data = [
        ("利苑酒家", 22.272, 113.573, 75, ["早茶", "粤式", "虾饺"], ["美食", "早茶粤菜"]),
        ("陶陶居茶楼", 22.233, 113.552, 68, ["早茶", "粤式", "老字号"], ["美食", "早茶粤菜"]),
        ("点心皇", 22.255, 113.572, 55, ["早茶", "粤式", "点心"], ["美食", "早茶粤菜"]),
        ("华发粤海茶楼", 22.244, 113.533, 80, ["早茶", "粤式", "环境好"], ["美食", "早茶粤菜"]),
        ("金悦轩", 22.238, 113.555, 65, ["早茶", "粤式", "凤爪"], ["美食", "早茶粤菜"]),
        ("翠华茶餐厅", 22.268, 113.568, 48, ["早茶", "粤式", "奶茶"], ["美食", "早茶粤菜"]),
    ]
    return [
        _base_poi(
            idx, name, lat, lng, price, "茶餐厅", tags, scene,
            hours="07:00-15:00", stay_min=55, queue_prone=True, queue_min=20,
            excitement=0.35, tranquility=0.4, culture=0.5, score=7,
        )
        for idx, (name, lat, lng, price, tags, scene) in enumerate(data, start=4768)
    ]


# ---------------------------------------------------------------------------
# Category 6: Desserts / cold drinks (8)
# ---------------------------------------------------------------------------
def desserts() -> list[dict]:
    data = [
        ("许留山(香洲店)", 22.270, 113.572, 30, ["甜品", "芒果", "消暑"], ["美食", "甜品消暑"]),
        ("满记甜品(吉大店)", 22.253, 113.571, 35, ["甜品", "榴莲", "消暑"], ["美食", "甜品消暑"]),
        ("糖水铺老字号", 22.235, 113.554, 18, ["甜品", "糖水", "传统"], ["美食", "甜品消暑"]),
        ("芒果冰室", 22.243, 113.534, 28, ["甜品", "芒果冰", "消暑"], ["美食", "甜品消暑"]),
        ("陈记双皮奶", 22.267, 113.570, 15, ["甜品", "双皮奶", "传统"], ["美食", "甜品消暑"]),
        ("椰子冰(拱北店)", 22.228, 113.553, 32, ["甜品", "椰子", "消暑"], ["美食", "甜品消暑"]),
        ("豆花西施", 22.258, 113.567, 12, ["甜品", "豆花", "消暑"], ["美食", "甜品消暑"]),
        ("冰室七号", 22.246, 113.538, 25, ["甜品", "刨冰", "消暑"], ["美食", "甜品消暑"]),
    ]
    return [
        _base_poi(
            idx, name, lat, lng, price, "甜品饮品", tags, scene,
            hours="10:00-22:30", stay_min=30,
            couples=True, family=True, solo=True, friends=True,
            excitement=0.4, tranquility=0.5, culture=0.15, score=6,
        )
        for idx, (name, lat, lng, price, tags, scene) in enumerate(data, start=4774)
    ]


# ---------------------------------------------------------------------------
# Category 7: Hengqin specialties (6)
# ---------------------------------------------------------------------------
def hengqin() -> list[dict]:
    data = [
        ("横琴蚝生态园", 22.122, 113.532, 120, ["生蚝", "横琴特色", "海鲜"], ["美食", "横琴特色", "海鲜大排档"]),
        ("横琴烧腊王", 22.118, 113.528, 45, ["烧腊", "横琴特色", "本地特色"], ["美食", "横琴特色"]),
        ("横琴渔村海鲜", 22.115, 113.535, 95, ["海鲜", "渔村", "现捞现做"], ["美食", "横琴特色", "海鲜大排档"]),
        ("琴澳大排档", 22.125, 113.538, 70, ["大排档", "横琴特色", "宵夜"], ["美食", "横琴特色"]),
        ("横琴老街濑粉", 22.110, 113.525, 22, ["濑粉", "横琴特色", "早餐"], ["美食", "横琴特色"]),
        ("蚝庄海鲜酒楼", 22.128, 113.542, 150, ["生蚝", "海鲜", "横琴特色", "宴请"], ["美食", "横琴特色", "海鲜大排档"]),
    ]
    return [
        _base_poi(
            idx, name, lat, lng, price, "正餐", tags, scene,
            hours="10:00-23:00", stay_min=55, queue_prone=("蚝" in name),
            pet_friendly=(i % 2 == 0),
            excitement=0.4, tranquility=0.35, culture=0.35, score=6,
        )
        for i, (idx, (name, lat, lng, price, tags, scene)) in enumerate(enumerate(data, start=4782))
    ]


def main() -> None:
    random.seed(42)

    # Read existing data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        pois = json.load(f)
    original_count = len(pois)
    print(f"Existing POIs: {original_count}")

    # Generate all new POIs
    new_pois: list[dict] = []
    new_pois.extend(vegetarian())
    new_pois.extend(romantic())
    new_pois.extend(doumen_jinwan())
    new_pois.extend(farmhouse())
    new_pois.extend(morning_tea())
    new_pois.extend(desserts())
    new_pois.extend(hengqin())

    print(f"New POIs to add: {len(new_pois)}")
    print(f"  ID range: {new_pois[0]['id']} - {new_pois[-1]['id']}")

    # Verify no ID collisions
    existing_ids = {p["id"] for p in pois}
    collisions = [p["id"] for p in new_pois if p["id"] in existing_ids]
    if collisions:
        raise ValueError(f"ID collisions found: {collisions}")

    # Append and write back
    pois.extend(new_pois)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(pois, f, ensure_ascii=False, indent=2)

    # Summary by category
    from collections import Counter
    display_cats = Counter(p["_display_category"] for p in new_pois)
    print(f"\nNew POIs by display_category:")
    for cat, cnt in display_cats.most_common():
        print(f"  {cat}: {cnt}")

    # Verify file
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        verify = json.load(f)
    print(f"\nVerification: {len(verify)} total POIs in file (expected {original_count + len(new_pois)})")
    print("Done.")


if __name__ == "__main__":
    main()
