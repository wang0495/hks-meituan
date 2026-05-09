"""数据库层单元测试。

测试 ORM 模型和 Repository 的基本 CRUD 操作。
使用 aiosqlite 内存数据库，不依赖 PostgreSQL。
"""

from __future__ import annotations

import uuid

import pytest

from backend.database.models import Route, User
from backend.database.repository import (DialogueRepository, RouteRepository,
                                         RouteStepRepository,
                                         UserPreferenceRepository,
                                         UserRepository)

# ---------------------------------------------------------------------------
# UserRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_user(user_repo: UserRepository) -> None:
    user = await user_repo.create()
    assert user.id is not None
    assert user.preferences == {}


@pytest.mark.asyncio
async def test_create_user_with_preferences(user_repo: UserRepository) -> None:
    user = await user_repo.create(preferences={"pace": "relaxed", "budget": 500})
    assert user.preferences["pace"] == "relaxed"


@pytest.mark.asyncio
async def test_get_user(user_repo: UserRepository, sample_user: User) -> None:
    found = await user_repo.get(sample_user.id)
    assert found is not None
    assert found.id == sample_user.id


@pytest.mark.asyncio
async def test_get_nonexistent_user(user_repo: UserRepository) -> None:
    found = await user_repo.get(uuid.uuid4())
    assert found is None


@pytest.mark.asyncio
async def test_update_preferences(user_repo: UserRepository, sample_user: User) -> None:
    updated = await user_repo.update_preferences(
        sample_user.id, {"pace": "adventure", "budget": 1000}
    )
    assert updated is not None
    assert updated.preferences["pace"] == "adventure"


# ---------------------------------------------------------------------------
# RouteRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_route(route_repo: RouteRepository, sample_user: User) -> None:
    route = await route_repo.create(
        user_input="和朋友吃喝玩乐",
        route_data={"route": []},
        user_id=sample_user.id,
    )
    assert route.id is not None
    assert route.user_input == "和朋友吃喝玩乐"
    assert route.status == "active"


@pytest.mark.asyncio
async def test_get_route(route_repo: RouteRepository, sample_route: Route) -> None:
    found = await route_repo.get(sample_route.id)
    assert found is not None
    assert found.user_input == "周末想一个人安静走走"


@pytest.mark.asyncio
async def test_get_routes_by_user(
    route_repo: RouteRepository, sample_route: Route, sample_user: User
) -> None:
    routes = await route_repo.get_by_user(sample_user.id)
    assert len(routes) >= 1
    assert routes[0].id == sample_route.id


@pytest.mark.asyncio
async def test_update_route(route_repo: RouteRepository, sample_route: Route) -> None:
    new_data = {"route": [{"poi": {"id": "poi_002", "name": "颐和园"}}]}
    updated = await route_repo.update(sample_route.id, new_data)
    assert updated is not None
    assert updated.route_data == new_data


@pytest.mark.asyncio
async def test_update_route_status(
    route_repo: RouteRepository, sample_route: Route
) -> None:
    updated = await route_repo.update_status(sample_route.id, "archived")
    assert updated is not None
    assert updated.status == "archived"


@pytest.mark.asyncio
async def test_delete_route(route_repo: RouteRepository, sample_route: Route) -> None:
    result = await route_repo.delete(sample_route.id)
    assert result is True
    found = await route_repo.get(sample_route.id)
    assert found is None


@pytest.mark.asyncio
async def test_delete_nonexistent_route(route_repo: RouteRepository) -> None:
    result = await route_repo.delete(uuid.uuid4())
    assert result is False


# ---------------------------------------------------------------------------
# RouteStepRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_create_steps(
    step_repo: RouteStepRepository, route_repo: RouteRepository, sample_route: Route
) -> None:
    steps_data = [
        {
            "step_index": 0,
            "poi_id": "poi_001",
            "poi_name": "故宫",
            "arrival_time": "09:00",
            "departure_time": "11:00",
            "travel_from_prev": None,
        },
        {
            "step_index": 1,
            "poi_id": "poi_002",
            "poi_name": "颐和园",
            "arrival_time": "12:00",
            "departure_time": "14:00",
            "travel_from_prev": {"distance_m": 15000, "time_min": 30},
        },
    ]
    steps = await step_repo.bulk_create(sample_route.id, steps_data)
    assert len(steps) == 2
    assert steps[0].poi_name == "故宫"
    assert steps[1].step_index == 1


@pytest.mark.asyncio
async def test_get_steps_by_route(
    step_repo: RouteStepRepository, route_repo: RouteRepository, sample_route: Route
) -> None:
    await step_repo.bulk_create(
        sample_route.id,
        [
            {"step_index": 0, "poi_id": "p1", "poi_name": "A"},
            {"step_index": 1, "poi_id": "p2", "poi_name": "B"},
        ],
    )
    steps = await step_repo.get_by_route(sample_route.id)
    assert len(steps) == 2
    assert steps[0].step_index == 0
    assert steps[1].step_index == 1


# ---------------------------------------------------------------------------
# DialogueRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_and_get_dialogue(
    dialogue_repo: DialogueRepository, sample_route: Route
) -> None:
    session_id = "test_session_001"
    msg = await dialogue_repo.add_message(
        route_id=sample_route.id,
        session_id=session_id,
        role="user",
        content="换掉第二个景点",
    )
    assert msg.id is not None
    assert msg.role == "user"

    await dialogue_repo.add_message(
        route_id=sample_route.id,
        session_id=session_id,
        role="assistant",
        content="好的，已为您替换",
    )

    messages = await dialogue_repo.get_session_messages(session_id)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"


# ---------------------------------------------------------------------------
# UserPreferenceRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_preference(
    pref_repo: UserPreferenceRepository, sample_user: User
) -> None:
    # 首次插入
    pref = await pref_repo.upsert(sample_user.id, "pace", {"value": "relaxed"})
    assert pref.preference_type == "pace"
    assert pref.preference_value == {"value": "relaxed"}

    # 更新
    pref2 = await pref_repo.upsert(sample_user.id, "pace", {"value": "adventure"})
    assert pref2.id == pref.id  # 同一条记录
    assert pref2.preference_value == {"value": "adventure"}


@pytest.mark.asyncio
async def test_get_all_preferences(
    pref_repo: UserPreferenceRepository, sample_user: User
) -> None:
    await pref_repo.upsert(sample_user.id, "pace", {"value": "relaxed"})
    await pref_repo.upsert(sample_user.id, "budget", {"max": 500})

    prefs = await pref_repo.get_all(sample_user.id)
    assert len(prefs) == 2
    types = {p.preference_type for p in prefs}
    assert types == {"pace", "budget"}
