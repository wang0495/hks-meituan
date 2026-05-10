"""硬编码补充 15 个珠海知名景点。"""
import json
from pathlib import Path

path = Path("backend/data/city_poi_db.json")
data = json.loads(path.read_text(encoding="utf-8"))
existing = {p["name"].strip() for p in data}
max_id = max(int(p["id"].split("_")[1]) for p in data if p["id"].startswith("poi_"))

FAMOUS = [
    {"name":"长隆海洋王国","cat":"景点","price":350,"lat":22.098,"lng":113.544,"stay":300,"tags":["亲子","乐园","海洋"],"scene":["亲子","打卡热点","拍照出片"],"suit":{"情侣友好":True,"亲子友好":True,"独自友好":False,"朋友友好":True},"emo":{"excitement":0.9,"tranquility":0.2,"sociability":0.8,"culture_depth":0.2,"surprise":0.9,"physical_demand":0.6},"rating":4.8,"hours":"10:00-20:30"},
    {"name":"情侣路","cat":"景点","price":0,"lat":22.268,"lng":113.575,"stay":120,"tags":["海滨","步行","浪漫"],"scene":["海滨","夜景","情侣","拍照出片"],"suit":{"情侣友好":True,"亲子友好":True,"独自友好":True,"朋友友好":True},"emo":{"excitement":0.5,"tranquility":0.8,"sociability":0.4,"culture_depth":0.2,"surprise":0.4,"physical_demand":0.3},"rating":4.7,"hours":"00:00-23:59"},
    {"name":"野狸岛","cat":"景点","price":0,"lat":22.278,"lng":113.571,"stay":90,"tags":["海岛","散步","自然"],"scene":["海滨","自然风光","休闲放松"],"suit":{"情侣友好":True,"亲子友好":True,"独自友好":True,"朋友友好":True},"emo":{"excitement":0.4,"tranquility":0.8,"sociability":0.3,"culture_depth":0.2,"surprise":0.5,"physical_demand":0.4},"rating":4.5,"hours":"00:00-23:59"},
    {"name":"圆明新园","cat":"文化","price":60,"lat":22.271,"lng":113.565,"stay":150,"tags":["古建","文化","园林"],"scene":["文化历史","拍照出片","品质体验"],"suit":{"情侣友好":True,"亲子友好":True,"独自友好":True,"朋友友好":True},"emo":{"excitement":0.4,"tranquility":0.7,"sociability":0.4,"culture_depth":0.9,"surprise":0.6,"physical_demand":0.4},"rating":4.6,"hours":"09:00-17:00"},
    {"name":"日月贝（珠海大剧院）","cat":"文化","price":80,"lat":22.282,"lng":113.568,"stay":120,"tags":["建筑","文化","演出"],"scene":["夜景","拍照出片","打卡热点"],"suit":{"情侣友好":True,"亲子友好":True,"独自友好":True,"朋友友好":True},"emo":{"excitement":0.7,"tranquility":0.5,"sociability":0.6,"culture_depth":0.7,"surprise":0.8,"physical_demand":0.2},"rating":4.7,"hours":"09:00-21:00"},
    {"name":"横琴国家湿地公园","cat":"运动","price":0,"lat":22.186,"lng":113.526,"stay":120,"tags":["湿地","自然","观鸟"],"scene":["自然风光","休闲放松","公园"],"suit":{"情侣友好":True,"亲子友好":True,"独自友好":True,"朋友友好":True},"emo":{"excitement":0.3,"tranquility":0.9,"sociability":0.2,"culture_depth":0.3,"surprise":0.6,"physical_demand":0.3},"rating":4.5,"hours":"09:00-18:00"},
    {"name":"石景山公园","cat":"运动","price":10,"lat":22.273,"lng":113.577,"stay":90,"tags":["山景","索道","登高"],"scene":["山景","自然风光","拍照出片"],"suit":{"情侣友好":True,"亲子友好":True,"独自友好":True,"朋友友好":True},"emo":{"excitement":0.5,"tranquility":0.6,"sociability":0.3,"culture_depth":0.2,"surprise":0.5,"physical_demand":0.6},"rating":4.4,"hours":"08:00-18:00"},
    {"name":"珠海海滨泳场","cat":"运动","price":0,"lat":22.260,"lng":113.578,"stay":120,"tags":["沙滩","游泳","阳光"],"scene":["海滨","休闲放松","亲子"],"suit":{"情侣友好":True,"亲子友好":True,"独自友好":True,"朋友友好":True},"emo":{"excitement":0.7,"tranquility":0.6,"sociability":0.6,"culture_depth":0.1,"surprise":0.4,"physical_demand":0.4},"rating":4.3,"hours":"06:00-22:00"},
    {"name":"爱情邮局（灯塔）","cat":"景点","price":0,"lat":22.257,"lng":113.579,"stay":45,"tags":["灯塔","浪漫","拍照"],"scene":["海滨","情侣","拍照出片","打卡热点"],"suit":{"情侣友好":True,"亲子友好":False,"独自友好":True,"朋友友好":True},"emo":{"excitement":0.6,"tranquility":0.7,"sociability":0.5,"culture_depth":0.2,"surprise":0.7,"physical_demand":0.1},"rating":4.5,"hours":"00:00-23:59"},
    {"name":"景山道","cat":"运动","price":0,"lat":22.270,"lng":113.573,"stay":90,"tags":["步道","观景","健身"],"scene":["山景","运动健身","自然风光"],"suit":{"情侣友好":True,"亲子友好":False,"独自友好":True,"朋友友好":True},"emo":{"excitement":0.4,"tranquility":0.7,"sociability":0.2,"culture_depth":0.2,"surprise":0.4,"physical_demand":0.7},"rating":4.3,"hours":"08:00-18:00"},
    {"name":"唐家湾古镇","cat":"文化","price":0,"lat":22.362,"lng":113.590,"stay":120,"tags":["古镇","历史","文艺"],"scene":["文化历史","休闲放松","拍照出片"],"suit":{"情侣友好":True,"亲子友好":True,"独自友好":True,"朋友友好":True},"emo":{"excitement":0.3,"tranquility":0.8,"sociability":0.4,"culture_depth":0.8,"surprise":0.5,"physical_demand":0.3},"rating":4.4,"hours":"00:00-23:59"},
    {"name":"金台寺","cat":"文化","price":0,"lat":22.285,"lng":113.379,"stay":60,"tags":["寺庙","祈福","宁静"],"scene":["文化历史","休闲放松","山景"],"suit":{"情侣友好":False,"亲子友好":True,"独自友好":True,"朋友友好":True},"emo":{"excitement":0.2,"tranquility":0.9,"sociability":0.2,"culture_depth":0.7,"surprise":0.3,"physical_demand":0.3},"rating":4.5,"hours":"08:00-17:00"},
    {"name":"梅溪牌坊","cat":"文化","price":50,"lat":22.310,"lng":113.482,"stay":90,"tags":["历史","建筑","文化"],"scene":["文化历史","拍照出片","经济实惠"],"suit":{"情侣友好":True,"亲子友好":True,"独自友好":True,"朋友友好":True},"emo":{"excitement":0.3,"tranquility":0.6,"sociability":0.3,"culture_depth":0.8,"surprise":0.5,"physical_demand":0.3},"rating":4.3,"hours":"09:00-17:00"},
    {"name":"农科奇观","cat":"景点","price":80,"lat":22.310,"lng":113.508,"stay":120,"tags":["科技","农业","亲子"],"scene":["亲子","自然风光","经济实惠"],"suit":{"情侣友好":False,"亲子友好":True,"独自友好":False,"朋友友好":False},"emo":{"excitement":0.5,"tranquility":0.5,"sociability":0.3,"culture_depth":0.5,"surprise":0.7,"physical_demand":0.3},"rating":4.2,"hours":"09:00-17:00"},
    {"name":"板樟山森林公园","cat":"运动","price":0,"lat":22.263,"lng":113.553,"stay":120,"tags":["森林","徒步","氧气"],"scene":["山景","自然风光","运动健身"],"suit":{"情侣友好":True,"亲子友好":True,"独自友好":True,"朋友友好":True},"emo":{"excitement":0.4,"tranquility":0.8,"sociability":0.2,"culture_depth":0.2,"surprise":0.4,"physical_demand":0.6},"rating":4.3,"hours":"08:00-18:00"},
]

added = 0
for p in FAMOUS:
    if p["name"] in existing:
        print(f"  SKIP: {p['name']} (已有)")
        continue
    max_id += 1
    data.append({
        "id": f"poi_{max_id:05d}",
        "name": p["name"],
        "city": "珠海",
        "category": p["cat"],
        "rating": p["rating"],
        "avg_price": p["price"],
        "lat": p["lat"],
        "lng": p["lng"],
        "business_hours": p["hours"],
        "tags": p["tags"],
        "queue_prone": False,
        "avg_stay_min": p["stay"],
        "ugc_comments": [],
        "emotion_tags": p["emo"],
        "constraints": {"accessible":True,"pet_friendly":False,"queue_time_min":5,"opening_hours":p["hours"]},
        "_scene_tags": p["scene"],
        "_suitability": p["suit"],
    })
    existing.add(p["name"])
    added += 1
    print(f"  ✅ ADD: {p['name']}")

path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n🎉 新增 {added} 个，总POI: {len(data)}")
print(f"珠海: {sum(1 for p in data if p.get('city')=='珠海')}")
