"""测试10个完美场景"""
import asyncio, json
from pathlib import Path
import httpx

BASE = 'http://localhost:8001'

async def test_scenario(sc):
    async with httpx.AsyncClient(timeout=120.0) as c:
        r = await c.post(f'{BASE}/api/plan', json={'user_input': sc['input']})

    route = []
    infeasible = None
    impossible = None
    current_event = None

    for line in r.text.split('\n'):
        line = line.strip()
        if line.startswith('event: '):
            current_event = line[7:].strip()
        elif line.startswith('data: '):
            try:
                data = json.loads(line[6:])
                if current_event == 'step':
                    route.append(data)
                elif current_event == 'agent_infeasible':
                    infeasible = data
                elif current_event == 'agent_impossible':
                    impossible = data
            except:
                pass

    return route, infeasible, impossible

async def main():
    scenarios = json.loads(Path('eval_data/perfect_scenarios.json').read_text(encoding='utf-8'))
    print(f'完美场景测试 — {len(scenarios)}个场景\n')

    results = []
    for sc in scenarios:
        name = sc['name']
        inp = sc['input']
        print(f'[{sc["id"]}] {name}: {inp[:40]}...')

        try:
            route, infeasible, impossible = await test_scenario(sc)

            if impossible:
                print(f'  [IntentAgent] 拒绝: {impossible.get("reason", "")[:40]}')
                print(f'  Status: ❌ 不合理拒绝')
                results.append({'name': name, 'status': 'rejected_unfairly', 'poi_count': 0})
                continue

            if infeasible:
                print(f'  [FeasibilityAgent] 拒绝: {infeasible.get("reason", "")[:40]}')
                print(f'  Status: ❌ 不合理拒绝')
                results.append({'name': name, 'status': 'rejected_unfairly', 'poi_count': 0})
                continue

            poi_count = len(route)
            cats = [s.get('poi',{}).get('category','?') for s in route]
            print(f'  路线: {" -> ".join(cats)} ({poi_count}站)')

            if poi_count >= 3:
                print(f'  Status: ✅ 通过')
                results.append({'name': name, 'status': 'pass', 'poi_count': poi_count})
            else:
                print(f'  Status: ❌ POI数量不足')
                results.append({'name': name, 'status': 'too_few_poi', 'poi_count': poi_count})

        except Exception as e:
            print(f'  Error: {e}')
            results.append({'name': name, 'status': 'error', 'poi_count': 0})

    # 统计
    passed = len([r for r in results if r['status'] == 'pass'])
    rejected = len([r for r in results if r['status'] == 'rejected_unfairly'])
    print(f'\n{"="*50}')
    print(f'结果: {passed}/{len(scenarios)} 通过 ({passed*10}%)')
    print(f'不合理拒绝: {rejected}个')
    print(f'{"="*50}')

if __name__ == '__main__':
    asyncio.run(main())
