"""Append ~30 new food POIs to city_poi_db.json.

Categories:
  1. Jinwan Airport quick meals (5)
  2. Hengqin specialty food (5)
  3. Romantic dinner (5)
  4. Afternoon tea / desserts (5)
  5. Farmhouse / Doumen (5)
  6. Morning dim sum (5)
"""

import json
from pathlib import Path

DATA_PATH = Path(r"C:\Users\wang\Desktop\hks美团\backend\data\city_poi_db.json")


def load_existing():
    """Load JSON and return (data, max_numeric_id)."""
    text = DATA_PATH.read_text(encoding="utf-8")
    data = json.loads(text)
    max_id = max(int(p["id"].split("_")[1]) for p in data)
    return data, max_id


def build_poi(seq, **kw):
    """Build a POI dict with sensible defaults, overridden by kw."""
    base = {
        "id": f"poi_{seq:05d}",
        "name": "",
        "city": "\u73e0\u6d77",
        "category": "\u9910\u996e",
        "rating": 4.2,
        "avg_price": 50,
        "lat": 22.270,
        "lng": 113.570,
        "business_hours": "10:00-22:00",
        "tags": [],
        "queue_prone": False,
        "avg_stay_min": 40,
        "ugc_comments": [],
        "emotion_tags": {
            "excitement": 0.5,
            "tranquility": 0.5,
            "sociability": 0.6,
            "culture_depth": 0.3,
            "surprise": 0.4,
            "physical_demand": 0.1,
        },
        "_scene_tags": ["\u7f8e\u98df"],
        "_suitability": {
            "\u60c5\u4fa3\u53cb\u597d": True,
            "\u4eb2\u5b50\u53cb\u597d": False,
            "\u72ec\u81ea\u53cb\u597d": True,
            "\u670b\u53cb\u53cb\u597d": True,
        },
        "_llm_quality": {"is_tourist": False, "score": 7, "issues": []},
        "constraints": {
            "accessible": True,
            "pet_friendly": False,
            "queue_time_min": 5,
            "opening_hours": "10:00-22:00",
        },
        "_display_category": "\u6b63\u9910",
    }
    base.update(kw)
    if "business_hours" in kw and "constraints" not in kw:
        base["constraints"]["opening_hours"] = kw["business_hours"]
    return base


def gen_airport():
    """Jinwan Airport quick meals -- 5 POIs."""
    return [
        build_poi(
            0,
            name="\u91d1\u6e7e\u673a\u573a\u5473\u5343\u62c9\u9762",
            rating=3.9,
            avg_price=38,
            lat=22.0480,
            lng=113.3780,
            business_hours="07:00-22:00",
            tags=["\u62c9\u9762", "\u65e5\u5f0f", "\u673a\u573a", "\u5feb\u9910"],
            avg_stay_min=25,
            ugc_comments=[
                {"user": "\u8fc7\u8def\u65c5\u5ba2", "rating": 4, "content": "\u8d76\u98de\u673a\u524d\u5feb\u901f\u89e3\u51b3\u4e00\u987f\uff0c\u6c64\u5934\u8fd8\u4e0d\u9519\uff0c\u9762\u6761\u7b4b\u9053\u3002"},
                {"user": "\u51fa\u5dee\u515a", "rating": 3, "content": "\u673a\u573a\u91cc\u7684\u4ef7\u683c\u561b\uff0c\u53ef\u4ee5\u7406\u89e3\uff0c\u5473\u9053\u4e2d\u89c4\u4e2d\u77e9\u3002"},
            ],
            _display_category="\u6b63\u9910",
        ),
        build_poi(
            0,
            name="\u673a\u573a\u5feb\u7ebf\u7ca5\u94fa",
            rating=4.1,
            avg_price=22,
            lat=22.0520,
            lng=113.3820,
            business_hours="06:00-21:30",
            tags=["\u7ca5", "\u65e9\u9910", "\u673a\u573a", "\u5730\u65b9\u5c0f\u5403"],
            avg_stay_min=20,
            ugc_comments=[
                {"user": "\u65e9\u73ed\u673a\u4e58\u5ba2", "rating": 4, "content": "\u65e9\u4e0a\u516d\u70b9\u5c31\u5f00\u95e8\uff0c\u8247\u4ed4\u7ca5\u6599\u8db3\u5473\u9c9c\uff0c\u8d76\u65e9\u73ed\u673a\u9996\u9009\u3002"},
            ],
            _display_category="\u5730\u65b9\u5c0f\u5403",
        ),
        build_poi(
            0,
            name="\u91d1\u6e7e\u8001\u5b57\u53f7\u70e7\u5473\u5e97",
            rating=4.3,
            avg_price=35,
            lat=22.0620,
            lng=113.3900,
            business_hours="10:30-21:00",
            tags=["\u70e7\u814a", "\u53c9\u70e7", "\u672c\u5730\u7279\u8272", "\u673a\u573a\u9644\u8fd1"],
            queue_prone=True,
            avg_stay_min=25,
            ugc_comments=[
                {"user": "\u8001\u995d", "rating": 5, "content": "\u53c9\u70e7\u534a\u80a5\u534a\u7626\uff0c\u871c\u6c41\u5165\u5473\uff0c\u914d\u767d\u996d\u7edd\u4e86\u3002\u996d\u70b9\u8981\u6392\u961f\u3002"},
                {"user": "\u672c\u5730\u4eba", "rating": 4, "content": "\u5f00\u4e86\u5341\u51e0\u5e74\u7684\u8001\u5e97\uff0c\u70e7\u9e45\u4e5f\u5f88\u6b63\u5b97\u3002"},
            ],
            _display_category="\u6b63\u9910",
            constraints={
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 15,
                "opening_hours": "10:30-21:00",
            },
        ),
        build_poi(
            0,
            name="\u822a\u7ad9\u697c\u9ea6\u5f53\u52b3",
            rating=3.6,
            avg_price=30,
            lat=22.0430,
            lng=113.3760,
            business_hours="06:00-23:00",
            tags=["\u6c49\u5821", "\u5feb\u9910", "\u8fde\u9501", "\u673a\u573a"],
            avg_stay_min=20,
            ugc_comments=[
                {"user": "\u5e26\u5a03\u65c5\u5ba2", "rating": 4, "content": "\u5b69\u5b50\u5c31\u8ba4\u9ea6\u5f53\u52b3\uff0c\u673a\u573a\u8fd9\u5bb6\u51fa\u9910\u633a\u5feb\u7684\u3002"},
            ],
            _display_category="\u6b63\u9910",
        ),
        build_poi(
            0,
            name="\u91d1\u6e7e\u4e91\u541e\u9762\u9986",
            rating=4.0,
            avg_price=20,
            lat=22.0550,
            lng=113.3850,
            business_hours="07:00-20:30",
            tags=["\u4e91\u541e", "\u9762\u98df", "\u5730\u65b9\u5c0f\u5403", "\u5e73\u4ef7"],
            avg_stay_min=20,
            ugc_comments=[
                {"user": "\u80cc\u5305\u5ba2", "rating": 4, "content": "\u9c9c\u867e\u4e91\u541e\u76ae\u8584\u9985\u5927\uff0c\u4e00\u7897\u624d15\u5757\uff0c\u673a\u573a\u9644\u8fd1\u6027\u4ef7\u6bd4\u4e4b\u738b\u3002"},
                {"user": "\u9644\u8fd1\u5c45\u6c11", "rating": 4, "content": "\u9762\u5e95\u78b1\u6c34\u9762\u5f88\u6b63\u5b97\uff0c\u6c64\u5934\u6e05\u751c\u3002"},
            ],
            _display_category="\u5730\u65b9\u5c0f\u5403",
        ),
    ]


def gen_hengqin():
    """Hengqin local specialties -- 5 POIs."""
    return [
        build_poi(
            0,
            name="\u6a2a\u7434\u869d\u5e84",
            rating=4.5,
            avg_price=95,
            lat=22.1200,
            lng=113.5300,
            business_hours="11:00-22:00",
            tags=["\u6a2a\u7434", "\u751f\u869d", "\u672c\u5730\u7279\u8272", "\u6d77\u9c9c"],
            queue_prone=True,
            avg_stay_min=60,
            ugc_comments=[
                {"user": "\u6d77\u9c9c\u63a7", "rating": 5, "content": "\u6a2a\u7434\u751f\u869d\u679c\u7136\u540d\u4e0d\u865a\u4f20\uff0c\u80a5\u7f8e\u591a\u6c41\uff0c\u78b3\u70e4\u548c\u523a\u8eab\u90fd\u8bd5\u4e86\uff0c\u7edd\uff01"},
                {"user": "\u6e38\u5ba2A", "rating": 4, "content": "\u4e13\u7a0b\u5f00\u8f66\u6765\u5403\uff0c\u751f\u869d\u5f88\u65b0\u9c9c\uff0c\u5c31\u662f\u5468\u672b\u4eba\u592a\u591a\u4e86\u3002"},
            ],
            emotion_tags={
                "excitement": 0.7,
                "tranquility": 0.3,
                "sociability": 0.8,
                "culture_depth": 0.4,
                "surprise": 0.6,
                "physical_demand": 0.1,
            },
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": True,
                "\u4eb2\u5b50\u53cb\u597d": True,
                "\u72ec\u81ea\u53cb\u597d": False,
                "\u670b\u53cb\u53cb\u597d": True,
            },
            _display_category="\u6b63\u9910",
            constraints={
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 20,
                "opening_hours": "11:00-22:00",
            },
        ),
        build_poi(
            0,
            name="\u6a2a\u7434\u6d77\u9c9c\u6e14\u6e2f",
            rating=4.3,
            avg_price=120,
            lat=22.1350,
            lng=113.5450,
            business_hours="10:30-22:00",
            tags=["\u6a2a\u7434", "\u6d77\u9c9c", "\u6e14\u6e2f", "\u672c\u5730\u7279\u8272", "\u5927\u6392\u6863"],
            avg_stay_min=70,
            ugc_comments=[
                {"user": "\u7f8e\u98df\u535a\u4e3b", "rating": 5, "content": "\u73b0\u635e\u73b0\u505a\uff0c\u818f\u87f9\u548c\u77f3\u6591\u9c7c\u90fd\u5f88\u8d5e\uff0c\u98df\u6750\u65b0\u9c9c\u5ea6\u6ee1\u5206\u3002"},
                {"user": "\u5bb6\u5ead\u805a\u9910", "rating": 4, "content": "\u4e00\u5bb6\u4eba\u6765\u5403\uff0c\u70b9\u4e86\u516d\u83dc\u4e00\u6c64\uff0c\u4eba\u5747\u4e00\u767e\u51fa\u5934\uff0c\u5f88\u5212\u7b97\u3002"},
            ],
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": True,
                "\u4eb2\u5b50\u53cb\u597d": True,
                "\u72ec\u81ea\u53cb\u597d": False,
                "\u670b\u53cb\u53cb\u597d": True,
            },
            _display_category="\u6b63\u9910",
        ),
        build_poi(
            0,
            name="\u6a2a\u7434\u6fd1\u5c3f\u867e\u5927\u6392\u6863",
            rating=4.2,
            avg_price=80,
            lat=22.1480,
            lng=113.5580,
            business_hours="16:00-02:00",
            tags=["\u6a2a\u7434", "\u6fd1\u5c3f\u867e", "\u5927\u6392\u6863", "\u591c\u5bb5", "\u672c\u5730\u7279\u8272"],
            avg_stay_min=55,
            ugc_comments=[
                {"user": "\u591c\u732b\u5b50", "rating": 4, "content": "\u6912\u76d0\u6fd1\u5c3f\u867e\u8089\u8d28Q\u5f39\uff0c\u591c\u5bb5\u6765\u4e00\u76d8\u914d\u5564\u9152\uff0c\u723d\u3002"},
                {"user": "\u73e0\u6d77\u901a", "rating": 5, "content": "\u8fd9\u624d\u662f\u6a2a\u7434\u6700\u63a5\u5730\u6c14\u7684\u5403\u6cd5\uff0c\u4e0d\u662f\u6e38\u5ba2\u5e97\u3002"},
            ],
            emotion_tags={
                "excitement": 0.8,
                "tranquility": 0.2,
                "sociability": 0.9,
                "culture_depth": 0.3,
                "surprise": 0.5,
                "physical_demand": 0.1,
            },
            _display_category="\u6b63\u9910",
        ),
        build_poi(
            0,
            name="\u6a2a\u7434\u5ba2\u5bb6\u83dc\u9986",
            rating=4.0,
            avg_price=65,
            lat=22.1100,
            lng=113.5200,
            business_hours="11:00-21:00",
            tags=["\u6a2a\u7434", "\u5ba2\u5bb6\u83dc", "\u917f\u8c46\u8150", "\u672c\u5730\u7279\u8272"],
            avg_stay_min=50,
            ugc_comments=[
                {"user": "\u5ba2\u5bb6\u4eba", "rating": 4, "content": "\u917f\u8c46\u8150\u6709\u5bb6\u91cc\u7684\u5473\u9053\uff0c\u76d0\u7119\u9e21\u4e5f\u5f88\u5730\u9053\u3002"},
                {"user": "\u8def\u8fc7", "rating": 4, "content": "\u91cf\u8db3\u5b9e\u60e0\uff0c\u4e09\u4e2a\u4eba\u70b9\u56db\u4e2a\u83dc\u5403\u4e0d\u5b8c\u3002"},
            ],
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": False,
                "\u4eb2\u5b50\u53cb\u597d": True,
                "\u72ec\u81ea\u53cb\u597d": False,
                "\u670b\u53cb\u53cb\u597d": True,
            },
            _display_category="\u6b63\u9910",
        ),
        build_poi(
            0,
            name="\u6a2a\u7434\u70e7\u9e45\u738b",
            rating=4.4,
            avg_price=55,
            lat=22.1550,
            lng=113.5700,
            business_hours="10:00-21:30",
            tags=["\u6a2a\u7434", "\u70e7\u9e45", "\u672c\u5730\u7279\u8272", "\u8001\u5b57\u53f7"],
            queue_prone=True,
            avg_stay_min=35,
            ugc_comments=[
                {"user": "\u70e7\u9e45\u8ff7", "rating": 5, "content": "\u76ae\u8106\u8089\u5ae9\uff0c\u6c41\u6c34\u5145\u76c8\uff0c\u6bd4\u5e02\u533a\u5f88\u591a\u70e7\u9e45\u5e97\u90fd\u597d\u5403\u3002"},
                {"user": "\u672c\u5730\u63a8\u8350", "rating": 4, "content": "\u6bcf\u6b21\u6765\u6a2a\u7434\u5fc5\u6253\u5305\u4e00\u53ea\u56de\u53bb\uff0c\u5916\u5356\u7a97\u53e3\u6c38\u8fdc\u5728\u6392\u961f\u3002"},
            ],
            _display_category="\u6b63\u9910",
            constraints={
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 15,
                "opening_hours": "10:00-21:30",
            },
        ),
    ]


def gen_romantic():
    """Romantic dinner spots -- 5 POIs."""
    return [
        build_poi(
            0,
            name="\u60c5\u4fa3\u8def\u6d77\u666f\u65e5\u6599",
            rating=4.6,
            avg_price=280,
            lat=22.2500,
            lng=113.5600,
            business_hours="11:30-14:00, 17:30-22:00",
            tags=["\u6d6a\u6f2b", "\u7ea6\u4f1a", "\u6d77\u666f", "\u65e5\u6599", "\u7cbe\u81f4"],
            avg_stay_min=90,
            ugc_comments=[
                {"user": "\u7eaa\u5ff5\u65e5", "rating": 5, "content": "\u5750\u5728\u7a97\u8fb9\u770b\u6d77\u5403omakase\uff0c\u6c1b\u56f4\u611f\u62c9\u6ee1\uff0c\u7ea6\u4f1a\u9996\u9009\u3002"},
                {"user": "\u5403\u8d27\u60c5\u4fa3", "rating": 5, "content": "\u523a\u8eab\u62fc\u76d8\u975e\u5e38\u65b0\u9c9c\uff0c\u670d\u52a1\u7ec6\u81f4\uff0c\u4ef7\u683c\u5bf9\u5f97\u8d77\u54c1\u8d28\u3002"},
            ],
            emotion_tags={
                "excitement": 0.5,
                "tranquility": 0.7,
                "sociability": 0.8,
                "culture_depth": 0.4,
                "surprise": 0.6,
                "physical_demand": 0.0,
            },
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": True,
                "\u4eb2\u5b50\u53cb\u597d": False,
                "\u72ec\u81ea\u53cb\u597d": False,
                "\u670b\u53cb\u53cb\u597d": False,
            },
            _display_category="\u6b63\u9910",
            constraints={
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 0,
                "opening_hours": "11:30-14:00, 17:30-22:00",
            },
        ),
        build_poi(
            0,
            name="\u4e5d\u6d32\u6e2f\u591c\u666f\u94c1\u677f\u70e7",
            rating=4.4,
            avg_price=220,
            lat=22.2350,
            lng=113.5750,
            business_hours="17:00-23:00",
            tags=["\u6d6a\u6f2b", "\u7ea6\u4f1a", "\u94c1\u677f\u70e7", "\u591c\u666f", "\u6d77\u666f"],
            avg_stay_min=80,
            ugc_comments=[
                {"user": "\u6c42\u5a5a\u6210\u529f", "rating": 5, "content": "\u94c1\u677f\u70e7\u8868\u6f14\u5f88\u6709\u6c1b\u56f4\uff0c\u591c\u666f\u914d\u4e0a\u7f8e\u98df\uff0c\u5f53\u665a\u6c42\u5a5a\u6210\u529f\uff01"},
                {"user": "\u5403\u8d27", "rating": 4, "content": "\u548c\u725b\u5165\u53e3\u5373\u5316\uff0c\u53a8\u5e08\u624b\u827a\u5f88\u597d\uff0c\u5c31\u662f\u4eba\u5747\u504f\u9ad8\u3002"},
            ],
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": True,
                "\u4eb2\u5b50\u53cb\u597d": False,
                "\u72ec\u81ea\u53cb\u597d": False,
                "\u670b\u53cb\u53cb\u597d": True,
            },
            _display_category="\u6b63\u9910",
        ),
        build_poi(
            0,
            name="\u60c5\u4fa3\u4e2d\u8def\u610f\u5927\u5229\u9910\u5385",
            rating=4.5,
            avg_price=200,
            lat=22.2650,
            lng=113.5550,
            business_hours="11:00-22:30",
            tags=["\u6d6a\u6f2b", "\u7ea6\u4f1a", "\u610f\u5927\u5229\u83dc", "\u6d77\u666f", "\u7ea2\u9152"],
            avg_stay_min=85,
            ugc_comments=[
                {"user": "\u7ea2\u9152\u7231\u597d\u8005", "rating": 5, "content": "\u624b\u5de5\u610f\u9762\u642d\u914d\u9152\u5e84\u76f4\u4f9b\u7ea2\u9152\uff0c\u7a97\u5916\u5c31\u662f\u5927\u6d77\uff0c\u592a\u6d6a\u6f2b\u4e86\u3002"},
                {"user": "\u7eaa\u5ff5\u65e5", "rating": 4, "content": "\u63d0\u62c9\u7c73\u82cf\u662f\u62db\u724c\uff0c\u73af\u5883\u5b89\u9759\uff0c\u9002\u5408\u804a\u5929\u3002"},
            ],
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": True,
                "\u4eb2\u5b50\u53cb\u597d": False,
                "\u72ec\u81ea\u53cb\u597d": False,
                "\u670b\u53cb\u53cb\u597d": True,
            },
            _display_category="\u6b63\u9910",
        ),
        build_poi(
            0,
            name="\u6e14\u5973\u65c1\u6d77\u9c9c\u897f\u9910\u5427",
            rating=4.3,
            avg_price=180,
            lat=22.2700,
            lng=113.5800,
            business_hours="12:00-23:00",
            tags=["\u6d6a\u6f2b", "\u7ea6\u4f1a", "\u897f\u9910", "\u6d77\u666f", "\u6d77\u9c9c"],
            avg_stay_min=75,
            ugc_comments=[
                {"user": "\u65c5\u6e38\u8fbe\u4eba", "rating": 4, "content": "\u878d\u5408\u4e86\u672c\u5730\u6d77\u9c9c\u548c\u897f\u5f0f\u505a\u6cd5\uff0c\u70e4\u9c88\u9c7c\u914d\u67e0\u6aac\u9171\u5f88\u6709\u521b\u610f\u3002"},
                {"user": "\u7ea6\u4f1a\u515a", "rating": 5, "content": "\u9732\u53f0\u5ea7\u4f4d\u76f4\u9762\u6e14\u5973\uff0c\u508d\u665a\u6765\u559d\u676f\u9e21\u5c3e\u9152\u770b\u65e5\u843d\uff0c\u5b8c\u7f8e\u3002"},
            ],
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": True,
                "\u4eb2\u5b50\u53cb\u597d": False,
                "\u72ec\u81ea\u53cb\u597d": True,
                "\u670b\u53cb\u53cb\u597d": True,
            },
            _display_category="\u6b63\u9910",
        ),
        build_poi(
            0,
            name="\u65e5\u843d\u89c2\u666f\u9910\u5385",
            rating=4.7,
            avg_price=350,
            lat=22.2400,
            lng=113.5400,
            business_hours="17:00-23:30",
            tags=["\u6d6a\u6f2b", "\u7ea6\u4f1a", "\u6d77\u666f", "\u65e5\u843d", "\u9ad8\u7aef"],
            avg_stay_min=100,
            ugc_comments=[
                {"user": "\u6c42\u5a5a\u7b56\u5212\u5e08", "rating": 5, "content": "\u5168\u73e0\u6d77\u6700\u9002\u5408\u6c42\u5a5a\u7684\u9910\u5385\u6ca1\u6709\u4e4b\u4e00\uff0c\u65e5\u843d\u65f6\u5206\u7f8e\u5f97\u50cf\u753b\u3002"},
                {"user": "\u8001\u5ba2\u6237", "rating": 5, "content": "\u6bcf\u5e74\u7eaa\u5ff5\u65e5\u90fd\u6765\uff0c\u83dc\u54c1\u4fdd\u6301\u6c34\u51c6\uff0c\u548c\u725b\u4e94\u5206\u719f\u662f\u5fc5\u70b9\u3002"},
            ],
            emotion_tags={
                "excitement": 0.6,
                "tranquility": 0.8,
                "sociability": 0.9,
                "culture_depth": 0.2,
                "surprise": 0.7,
                "physical_demand": 0.0,
            },
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": True,
                "\u4eb2\u5b50\u53cb\u597d": False,
                "\u72ec\u81ea\u53cb\u597d": False,
                "\u670b\u53cb\u53cb\u597d": False,
            },
            _display_category="\u6b63\u9910",
            constraints={
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 0,
                "opening_hours": "17:00-23:30",
            },
        ),
    ]


def gen_dessert():
    """Afternoon tea and desserts -- 5 POIs."""
    return [
        build_poi(
            0,
            name="\u534a\u5c9b\u9152\u5e97\u4e0b\u5348\u8336",
            rating=4.4,
            avg_price=48,
            lat=22.2700,
            lng=113.5750,
            business_hours="14:00-18:00",
            tags=["\u4e0b\u5348\u8336", "\u751c\u54c1", "\u82f1\u5f0f", "\u9152\u5e97"],
            avg_stay_min=60,
            ugc_comments=[
                {"user": "\u95fa\u871c\u56e2", "rating": 5, "content": "\u4e09\u5c42\u5854\u7cbe\u81f4\u597d\u770b\uff0c\u53f8\u5eb7\u997c\u914d\u51dd\u8102\u5976\u6cb9\u5f88\u5730\u9053\uff0c\u62cd\u7167\u8d85\u51fa\u7247\u3002"},
                {"user": "\u751c\u54c1\u63a7", "rating": 4, "content": "\u751c\u800c\u4e0d\u817b\uff0c\u7ea2\u8336\u53ef\u4ee5\u7eed\uff0c\u4eba\u5747\u4e94\u5341\u5f88\u503c\u3002"},
            ],
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": True,
                "\u4eb2\u5b50\u53cb\u597d": True,
                "\u72ec\u81ea\u53cb\u597d": True,
                "\u670b\u53cb\u53cb\u597d": True,
            },
            _display_category="\u751c\u54c1\u996e\u54c1",
            constraints={
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 5,
                "opening_hours": "14:00-18:00",
            },
        ),
        build_poi(
            0,
            name="\u73e0\u6d77\u8292\u679c\u73ed\u621f\u5c4b",
            rating=4.2,
            avg_price=28,
            lat=22.2500,
            lng=113.5400,
            business_hours="10:00-22:00",
            tags=["\u751c\u54c1", "\u8292\u679c", "\u73ed\u621f", "\u6d88\u6691"],
            avg_stay_min=30,
            ugc_comments=[
                {"user": "\u8292\u679c\u63a7", "rating": 5, "content": "\u73b0\u505a\u7684\u8292\u679c\u73ed\u621f\u76ae\u8584\u9985\u591a\uff0c\u8292\u679c\u8089\u8d85\u5927\u5757\uff01"},
                {"user": "\u590f\u5929\u5fc5\u5907", "rating": 4, "content": "\u6768\u679d\u7518\u9732\u4e5f\u5f88\u597d\u559d\uff0c\u590f\u5929\u6765\u4e00\u7897\u89e3\u6691\u3002"},
            ],
            _display_category="\u751c\u54c1\u996e\u54c1",
        ),
        build_poi(
            0,
            name="\u534e\u53d1\u5546\u90fd\u751c\u54c1\u5b9e\u9a8c\u5ba4",
            rating=4.3,
            avg_price=35,
            lat=22.2300,
            lng=113.5200,
            business_hours="10:00-22:00",
            tags=["\u751c\u54c1", "\u521b\u610f", "\u4e0b\u5348\u8336", "\u7f51\u7ea2"],
            avg_stay_min=35,
            ugc_comments=[
                {"user": "\u63a2\u5e97\u535a\u4e3b", "rating": 4, "content": "\u5206\u5b50\u6599\u7406\u98ce\u683c\u751c\u54c1\uff0c\u989c\u503c\u548c\u5473\u9053\u53cc\u5728\u7ebf\uff0c\u62cd\u7167\u5fc5\u6765\u3002"},
                {"user": "\u60c5\u4fa3", "rating": 4, "content": "\u53cc\u4eba\u5957\u9910\u8bbe\u8ba1\u5f97\u5f88\u7528\u5fc3\uff0c\u6bcf\u9053\u90fd\u6709\u60ca\u559c\u3002"},
            ],
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": True,
                "\u4eb2\u5b50\u53cb\u597d": False,
                "\u72ec\u81ea\u53cb\u597d": True,
                "\u670b\u53cb\u53cb\u597d": True,
            },
            _display_category="\u751c\u54c1\u996e\u54c1",
        ),
        build_poi(
            0,
            name="\u62f1\u5317\u6e2f\u5f0f\u7cd6\u6c34\u94fa",
            rating=4.1,
            avg_price=22,
            lat=22.2150,
            lng=113.5300,
            business_hours="12:00-23:00",
            tags=["\u751c\u54c1", "\u6e2f\u5f0f", "\u7cd6\u6c34", "\u6d88\u6691"],
            avg_stay_min=25,
            ugc_comments=[
                {"user": "\u6e2f\u98ce\u7231\u597d\u8005", "rating": 4, "content": "\u829d\u9ebb\u7cca\u548c\u674f\u4ec1\u971c\u90fd\u5f88\u6d53\u7a20\uff0c\u8ddf\u5728\u9999\u6e2f\u5403\u7684\u4e00\u6837\u3002"},
                {"user": "\u591c\u5bb5\u515a", "rating": 4, "content": "\u665a\u4e0a\u6765\u7897\u7ea2\u8c46\u6c99\uff0c\u751c\u5ea6\u521a\u521a\u597d\u3002"},
            ],
            _display_category="\u751c\u54c1\u996e\u54c1",
        ),
        build_poi(
            0,
            name="\u5409\u5927\u6d77\u8fb9\u51b0\u6dc7\u6dcb\u5427",
            rating=4.0,
            avg_price=25,
            lat=22.2600,
            lng=113.5700,
            business_hours="10:00-21:00",
            tags=["\u51b0\u6dc7\u6dcb", "\u6d88\u6691", "\u6d77\u666f", "\u751c\u54c1"],
            avg_stay_min=20,
            ugc_comments=[
                {"user": "\u590f\u5929\u5e38\u5ba2", "rating": 4, "content": "\u6d77\u76d0\u5473\u51b0\u6dc7\u6dcb\u5750\u5728\u6d77\u8fb9\u5403\uff0c\u914d\u7740\u6d77\u98ce\uff0c\u592a\u8212\u670d\u4e86\u3002"},
                {"user": "\u5e26\u5a03", "rating": 4, "content": "\u5b69\u5b50\u6700\u559c\u6b22\u5f69\u8679\u5473\u7684\uff0c\u989c\u8272\u597d\u770b\u5473\u9053\u4e5f\u597d\u3002"},
            ],
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": True,
                "\u4eb2\u5b50\u53cb\u597d": True,
                "\u72ec\u81ea\u53cb\u597d": True,
                "\u670b\u53cb\u53cb\u597d": True,
            },
            _display_category="\u751c\u54c1\u996e\u54c1",
        ),
    ]


def gen_farmhouse():
    """Farmhouse / Doumen -- 5 POIs."""
    return [
        build_poi(
            0,
            name="\u83b2\u6c5f\u519c\u5e84\u571f\u9e21\u9986",
            rating=4.4,
            avg_price=55,
            lat=22.2400,
            lng=113.2800,
            business_hours="10:00-20:00",
            tags=["\u519c\u5bb6\u83dc", "\u571f\u9e21", "\u672c\u5730\u7279\u8272", "\u7530\u56ed"],
            avg_stay_min=60,
            ugc_comments=[
                {"user": "\u81ea\u9a7e\u6e38", "rating": 5, "content": "\u8d70\u5730\u9e21\u73b0\u6293\u73b0\u505a\uff0c\u767d\u5207\u9e21\u5ae9\u6ed1\uff0c\u9e21\u6cb9\u996d\u9999\u5230\u4e0d\u884c\u3002"},
                {"user": "\u5bb6\u5ead\u51fa\u6e38", "rating": 4, "content": "\u9662\u5b50\u91cc\u5403\u996d\uff0c\u5c0f\u670b\u53cb\u53ef\u4ee5\u770b\u9e21\u9e2d\uff0c\u6311\u6709\u4e50\u8da3\u3002"},
            ],
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": False,
                "\u4eb2\u5b50\u53cb\u597d": True,
                "\u72ec\u81ea\u53cb\u597d": False,
                "\u670b\u53cb\u53cb\u597d": True,
            },
            _display_category="\u6b63\u9910",
        ),
        build_poi(
            0,
            name="\u6597\u95e8\u9ec4\u6768\u6cb3\u7554\u519c\u5bb6\u83dc",
            rating=4.2,
            avg_price=50,
            lat=22.2100,
            lng=113.2600,
            business_hours="10:30-20:30",
            tags=["\u519c\u5bb6\u83dc", "\u6cb3\u9c9c", "\u672c\u5730\u7279\u8272", "\u6597\u95e8"],
            avg_stay_min=55,
            ugc_comments=[
                {"user": "\u6597\u95e8\u901a", "rating": 4, "content": "\u6cb3\u867e\u548c\u9ec4\u9c57\u90fd\u662f\u91ce\u751f\u7684\uff0c\u6cb3\u7554\u5403\u996d\u98ce\u666f\u4e5f\u597d\u3002"},
                {"user": "\u5468\u672b\u4f11\u95f2", "rating": 4, "content": "\u8fdc\u79bb\u57ce\u5e02\u55a7\u56a3\uff0c\u5403\u987f\u519c\u5bb6\u996d\uff0c\u5f88\u653e\u677e\u3002"},
            ],
            emotion_tags={
                "excitement": 0.3,
                "tranquility": 0.8,
                "sociability": 0.6,
                "culture_depth": 0.5,
                "surprise": 0.3,
                "physical_demand": 0.1,
            },
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": True,
                "\u4eb2\u5b50\u53cb\u597d": True,
                "\u72ec\u81ea\u53cb\u597d": False,
                "\u670b\u53cb\u53cb\u597d": True,
            },
            _display_category="\u6b63\u9910",
        ),
        build_poi(
            0,
            name="\u4e95\u5cb8\u70e7\u814a\u8001\u5e97",
            rating=4.5,
            avg_price=40,
            lat=22.2300,
            lng=113.2900,
            business_hours="08:00-19:00",
            tags=["\u70e7\u814a", "\u672c\u5730\u7279\u8272", "\u8001\u5b57\u53f7", "\u6597\u95e8"],
            queue_prone=True,
            avg_stay_min=25,
            ugc_comments=[
                {"user": "\u6597\u95e8\u571f\u8457", "rating": 5, "content": "\u5f00\u4e86\u4e09\u5341\u5e74\u7684\u8001\u5e97\uff0c\u70e7\u9e45\u76ae\u8106\u8089\u5ae9\uff0c\u6bcf\u5929\u9650\u91cf\u5356\u5b8c\u5373\u6b62\u3002"},
                {"user": "\u7f8e\u98df\u730e\u4eba", "rating": 5, "content": "\u8fd9\u624d\u662f\u771f\u6b63\u7684\u6597\u95e8\u5473\u9053\uff0c\u6bd4\u5e02\u533a\u70e7\u814a\u5e97\u5f3a\u5341\u500d\u3002"},
            ],
            _display_category="\u6b63\u9910",
            constraints={
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 15,
                "opening_hours": "08:00-19:00",
            },
        ),
        build_poi(
            0,
            name="\u6597\u95e8\u767d\u85e4\u6e56\u9c7c\u5e84",
            rating=4.3,
            avg_price=65,
            lat=22.2600,
            lng=113.3100,
            business_hours="10:00-21:00",
            tags=["\u519c\u5bb6\u83dc", "\u9c7c", "\u767d\u85e4\u6e56", "\u672c\u5730\u7279\u8272"],
            avg_stay_min=55,
            ugc_comments=[
                {"user": "\u9493\u9c7c\u7231\u597d\u8005", "rating": 4, "content": "\u81ea\u5df1\u9493\u7684\u9c7c\u8ba9\u53a8\u5e08\u505a\uff0c\u4e00\u9c7c\u4e09\u5403\uff0c\u592a\u6709\u6210\u5c31\u611f\u4e86\u3002"},
                {"user": "\u5bb6\u5ead\u805a\u9910", "rating": 5, "content": "\u9c7c\u5934\u6c64\u5976\u767d\u6d53\u90c1\uff0c\u5b69\u5b50\u559d\u4e86\u4e24\u5927\u7897\u3002"},
            ],
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": False,
                "\u4eb2\u5b50\u53cb\u597d": True,
                "\u72ec\u81ea\u53cb\u597d": False,
                "\u670b\u53cb\u53cb\u597d": True,
            },
            _display_category="\u6b63\u9910",
        ),
        build_poi(
            0,
            name="\u83b2\u6d32\u7530\u56ed\u9910\u5385",
            rating=4.1,
            avg_price=45,
            lat=22.2750,
            lng=113.3200,
            business_hours="09:00-20:00",
            tags=["\u519c\u5bb6\u83dc", "\u7530\u56ed", "\u672c\u5730\u7279\u8272", "\u6709\u673a\u852c\u83dc"],
            avg_stay_min=50,
            ugc_comments=[
                {"user": "\u6709\u673a\u63a7", "rating": 4, "content": "\u852c\u83dc\u662f\u81ea\u5bb6\u79cd\u7684\uff0c\u6e05\u7092\u5c31\u5f88\u751c\uff0c\u571f\u732a\u8089\u4e5f\u5f88\u9999\u3002"},
                {"user": "\u4eb2\u5b50\u5bb6\u5ead", "rating": 4, "content": "\u65c1\u8fb9\u6709\u83dc\u5730\u53ef\u4ee5\u6458\u83dc\uff0c\u5c0f\u670b\u53cb\u73a9\u5f97\u5f88\u5f00\u5fc3\u3002"},
            ],
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": False,
                "\u4eb2\u5b50\u53cb\u597d": True,
                "\u72ec\u81ea\u53cb\u597d": False,
                "\u670b\u53cb\u53cb\u597d": True,
            },
            _display_category="\u6b63\u9910",
        ),
    ]


def gen_dimsum():
    """Morning dim sum -- 5 POIs."""
    return [
        build_poi(
            0,
            name="\u9676\u9676\u5c45\u73e0\u6d77\u5e97",
            rating=4.5,
            avg_price=68,
            lat=22.2500,
            lng=113.5500,
            business_hours="07:30-15:00, 17:00-21:30",
            tags=["\u65e9\u8336", "\u7ca4\u5f0f", "\u70b9\u5fc3", "\u8001\u5b57\u53f7"],
            queue_prone=True,
            avg_stay_min=70,
            ugc_comments=[
                {"user": "\u65e9\u8336\u7231\u597d\u8005", "rating": 5, "content": "\u867e\u997a\u7687\u548c\u51e4\u722a\u662f\u5fc5\u70b9\uff0c\u76ae\u8584\u9985\u5927\uff0c\u8ddf\u5e7f\u5dde\u603b\u5e97\u6709\u5f97\u4e00\u6bd4\u3002"},
                {"user": "\u5468\u672b\u6392\u961f", "rating": 4, "content": "\u5468\u672b\u8981\u7b49\u4f4d\uff0c\u4f46\u503c\u5f97\u3002\u80a0\u7c89\u6ed1\u5ae9\uff0c\u8c46\u6d46\u6d53\u90c1\u3002"},
            ],
            _suitability={
                "\u60c5\u4fa3\u53cb\u597d": False,
                "\u4eb2\u5b50\u53cb\u597d": True,
                "\u72ec\u81ea\u53cb\u597d": False,
                "\u670b\u53cb\u53cb\u597d": True,
            },
            _display_category="\u8336\u9910\u5385",
            constraints={
                "accessible": True,
                "pet_friendly": False,
                "queue_time_min": 20,
                "opening_hours": "07:30-15:00, 17:00-21:30",
            },
        ),
        build_poi(
            0,
            name="\u91d1\u60a6\u8f69\u65e9\u8336",
            rating=4.3,
            avg_price=55,
            lat=22.2400,
            lng=113.5350,
            business_hours="07:00-14:30, 17:30-21:00",
            tags=["\u65e9\u8336", "\u7ca4\u5f0f", "\u70b9\u5fc3", "\u7cbe\u81f4"],
            avg_stay_min=60,
            ugc_comments=[
                {"user": "\u8001\u5e7f", "rating": 4, "content": "\u6d41\u6c99\u5305\u548c\u9a6c\u8e44\u7cd5\u505a\u5f97\u597d\uff0c\u73af\u5883\u4e5f\u5e72\u51c0\u3002"},
                {"user": "\u5bb6\u5ead", "rating": 5, "content": "\u5e26\u8001\u4eba\u6765\u559d\u65e9\u8336\uff0c\u70b9\u5fc3\u54c1\u79cd\u591a\uff0c\u53e3\u5473\u5730\u9053\u3002"},
            ],
            _display_category="\u8336\u9910\u5385",
        ),
        build_poi(
            0,
            name="\u7fe0\u5fae\u8def\u70b9\u5fc3\u7687",
            rating=4.1,
            avg_price=40,
            lat=22.2200,
            lng=113.5450,
            business_hours="06:30-14:00",
            tags=["\u65e9\u8336", "\u7ca4\u5f0f", "\u70b9\u5fc3", "\u5e73\u4ef7"],
            avg_stay_min=45,
            ugc_comments=[
                {"user": "\u8857\u574a", "rating": 4, "content": "\u5f00\u4e86\u5f88\u591a\u5e74\u7684\u8336\u697c\uff0c\u4ef7\u683c\u5b9e\u60e0\uff0c\u53c9\u70e7\u5305\u5f88\u5927\u4e2a\u3002"},
                {"user": "\u65e9\u9910\u6253\u5361", "rating": 4, "content": "\u80a0\u7c89\u548c\u53ca\u7b2c\u7ca5\u662f\u7edd\u914d\uff0c\u4eba\u5747\u56db\u5341\u5403\u5230\u6491\u3002"},
            ],
            _display_category="\u8336\u9910\u5385",
        ),
        build_poi(
            0,
            name="\u62f1\u5317\u83b2\u6eaa\u8336\u697c",
            rating=4.2,
            avg_price=45,
            lat=22.2100,
            lng=113.5300,
            business_hours="06:00-14:00, 17:00-21:30",
            tags=["\u65e9\u8336", "\u7ca4\u5f0f", "\u70b9\u5fc3", "\u62f1\u5317"],
            avg_stay_min=50,
            ugc_comments=[
                {"user": "\u6e2f\u5ba2", "rating": 4, "content": "\u8fc7\u5173\u6765\u559d\u65e9\u8336\uff0c\u6bd4\u9999\u6e2f\u4fbf\u5b9c\u5f88\u591a\uff0c\u5473\u9053\u4e5f\u4e0d\u5dee\u3002"},
                {"user": "\u65e9\u9e1f", "rating": 5, "content": "\u516d\u70b9\u5f00\u95e8\uff0c\u7b2c\u4e00\u7b3c\u6700\u9c9c\uff0c\u86cb\u631d\u51fa\u7089\u5fc5\u62a2\u3002"},
            ],
            _display_category="\u8336\u9910\u5385",
        ),
        build_poi(
            0,
            name="\u5409\u5927\u6d77\u6e7e\u65e9\u8336\u574a",
            rating=4.0,
            avg_price=38,
            lat=22.2550,
            lng=113.5650,
            business_hours="07:00-13:30",
            tags=["\u65e9\u8336", "\u7ca4\u5f0f", "\u70b9\u5fc3", "\u6d77\u666f"],
            avg_stay_min=45,
            ugc_comments=[
                {"user": "\u9000\u4f11\u963f\u4f2f", "rating": 4, "content": "\u6bcf\u5929\u6765\u8fd9\u559d\u58f6\u666e\u6d31\u770b\u4efd\u62a5\u7eb8\uff0c\u9760\u7740\u7a97\u80fd\u770b\u5230\u6d77\uff0c\u60ec\u610f\u3002"},
                {"user": "\u6e38\u5ba2", "rating": 4, "content": "\u7b80\u5355\u5b9e\u5728\u7684\u65e9\u8336\u5e97\uff0c\u70e7\u5356\u548c\u7cef\u7c73\u9e21\u90fd\u4e0d\u9519\u3002"},
            ],
            emotion_tags={
                "excitement": 0.2,
                "tranquility": 0.8,
                "sociability": 0.5,
                "culture_depth": 0.6,
                "surprise": 0.2,
                "physical_demand": 0.0,
            },
            _display_category="\u8336\u9910\u5385",
        ),
    ]


def main():
    data, max_id = load_existing()
    start = max_id + 1

    all_new = (
        gen_airport()
        + gen_hengqin()
        + gen_romantic()
        + gen_dessert()
        + gen_farmhouse()
        + gen_dimsum()
    )

    for i, poi in enumerate(all_new):
        poi["id"] = f"poi_{start + i:05d}"

    data.extend(all_new)

    DATA_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Added {len(all_new)} POIs (IDs poi_{start:05d} .. poi_{start + len(all_new) - 1:05d})")
    print(f"Total POIs now: {len(data)}")


if __name__ == "__main__":
    main()
