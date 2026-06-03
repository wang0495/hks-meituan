"""降级策略单元测试。"""

from __future__ import annotations

import pytest

from backend.services.fallback import (
    fallback,
    fallback_emotion_analysis,
    fallback_llm_chat,
    fallback_narrative_generation,
    fallback_poi_search,
    fallback_route_planning,
)


class TestFallbackDecorator:
    @pytest.mark.asyncio
    async def test_no_fallback_on_success(self) -> None:
        @fallback(fallback_route_planning)
        async def succeed() -> dict:
            return {"route": ["a", "b"], "fallback": False}

        result = await succeed()
        assert result["fallback"] is False
        assert result["route"] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self) -> None:
        @fallback(fallback_route_planning)
        async def fail() -> dict:
            raise TimeoutError("timeout")

        result = await fail()
        assert result["fallback"] is True

    @pytest.mark.asyncio
    async def test_only_catches_specified_exceptions(self) -> None:
        @fallback(fallback_route_planning, exceptions=(TimeoutError,))
        async def raise_value_error() -> dict:
            raise ValueError("wrong type")

        with pytest.raises(ValueError):
            await raise_value_error()

    @pytest.mark.asyncio
    async def test_fallback_receives_original_args(self) -> None:
        received_args: list = []

        async def my_fallback(*args, **kwargs):
            received_args.extend(args)
            return {"fallback": True}

        @fallback(my_fallback)
        async def fail_with_args(a: str, b: int) -> dict:
            raise RuntimeError("fail")

        await fail_with_args("hello", 42)
        assert received_args == ["hello", 42]

    @pytest.mark.asyncio
    async def test_fallback_failure_raises(self) -> None:
        """降级函数本身也失败时，应该抛出异常。"""

        async def broken_fallback(*args, **kwargs):
            raise RuntimeError("fallback also broken")

        @fallback(broken_fallback)
        async def fail() -> dict:
            raise TimeoutError("original")

        with pytest.raises(RuntimeError, match="fallback also broken"):
            await fail()

    def test_sync_function_support(self) -> None:
        def sync_fallback():
            return {"fallback": True}

        @fallback(sync_fallback)
        def sync_fail() -> dict:
            raise OSError("fail")

        result = sync_fail()
        assert result["fallback"] is True


class TestPredefinedFallbacks:
    @pytest.mark.asyncio
    async def test_fallback_route_planning_shape(self) -> None:
        result = await fallback_route_planning()
        assert "route" in result
        assert result["route"] == []
        assert result["fallback"] is True
        assert "narrative" in result

    @pytest.mark.asyncio
    async def test_fallback_poi_search_shape(self) -> None:
        result = await fallback_poi_search()
        assert result["pois"] == []
        assert result["fallback"] is True

    @pytest.mark.asyncio
    async def test_fallback_narrative_generation_shape(self) -> None:
        result = await fallback_narrative_generation()
        assert "opening" in result
        assert "steps" in result
        assert "closing" in result
        assert result["fallback"] is True

    @pytest.mark.asyncio
    async def test_fallback_llm_chat_returns_string(self) -> None:
        result = await fallback_llm_chat()
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_fallback_emotion_analysis_shape(self) -> None:
        result = await fallback_emotion_analysis()
        expected_keys = {
            "excitement",
            "tranquility",
            "sociability",
            "culture_depth",
            "surprise",
            "physical_demand",
        }
        assert set(result.keys()) == expected_keys
        assert all(0 <= v <= 1 for v in result.values())
