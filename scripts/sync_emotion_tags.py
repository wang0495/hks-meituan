"""将 backend/data/city_poi_db.json 的 emotion_tags 同步到 frontend/data/city_poi_db.json"""

import json
from pathlib import Path

BASE = Path(__file__).parent
BACKEND_FILE = BASE / "backend" / "data" / "city_poi_db.json"
FRONTEND_FILE = BASE / "frontend" / "data" / "city_poi_db.json"


def main() -> None:
    backend_data: list[dict] = json.loads(BACKEND_FILE.read_text(encoding="utf-8"))
    frontend_data: list[dict] = json.loads(FRONTEND_FILE.read_text(encoding="utf-8"))

    # backend 按 id 建索引
    backend_map: dict[str, dict] = {poi["id"]: poi for poi in backend_data}

    synced = 0
    missing = 0
    for poi in frontend_data:
        bid = poi["id"]
        if bid in backend_map and "emotion_tags" in backend_map[bid]:
            poi["emotion_tags"] = backend_map[bid]["emotion_tags"]
            synced += 1
        else:
            missing += 1

    FRONTEND_FILE.write_text(
        json.dumps(frontend_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 验证
    verify_data: list[dict] = json.loads(FRONTEND_FILE.read_text(encoding="utf-8"))
    has_tags = sum(1 for p in verify_data if "emotion_tags" in p)

    print(f"backend POI 数量: {len(backend_data)}")
    print(f"frontend POI 数量: {len(frontend_data)}")
    print(f"成功同步: {synced}")
    print(f"未匹配/无emotion_tags: {missing}")
    print(f"验证 - frontend 中有 emotion_tags 的条目: {has_tags}/{len(verify_data)}")


if __name__ == "__main__":
    main()
