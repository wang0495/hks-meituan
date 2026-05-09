"""CityFlow 模板引擎测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment

from backend.services.template_engine import (TemplateCache, TemplateEngine,
                                              TemplateRenderError,
                                              get_template_engine,
                                              render_string,
                                              reset_template_engine)

# ---------------------------------------------------------------------------
# TemplateCache 测试
# ---------------------------------------------------------------------------


class TestTemplateCache:
    """模板缓存单元测试。"""

    def test_set_and_get(self):
        """存入后能取出。"""
        cache = TemplateCache(max_size=10, ttl_seconds=60)
        env = _make_env()
        tpl = env.from_string("hello {{ name }}")
        cache.set("k1", tpl)

        result = cache.get("k1")
        assert result is not None
        assert result.render(name="world") == "hello world"
        assert cache.hits == 1
        assert cache.misses == 0

    def test_miss_returns_none(self):
        """未存入的键返回 None。"""
        cache = TemplateCache()
        assert cache.get("missing") is None
        assert cache.misses == 1

    def test_ttl_expiration(self):
        """过期条目返回 None。"""
        cache = TemplateCache(max_size=10, ttl_seconds=0)
        env = _make_env()
        tpl = env.from_string("expired")
        cache.set("k1", tpl)
        # TTL=0，立即过期
        assert cache.get("k1") is None

    def test_lru_eviction(self):
        """满时淘汰最旧条目。"""
        cache = TemplateCache(max_size=2, ttl_seconds=60)
        env = _make_env()

        cache.set("a", env.from_string("a"))
        cache.set("b", env.from_string("b"))
        cache.set("c", env.from_string("c"))  # 淘汰 "a"

        assert cache.get("a") is None
        assert cache.get("b") is not None
        assert cache.get("c") is not None

    def test_invalidate(self):
        """手动删除缓存条目。"""
        cache = TemplateCache()
        env = _make_env()
        cache.set("k1", env.from_string("x"))
        assert cache.invalidate("k1") is True
        assert cache.get("k1") is None
        assert cache.invalidate("nonexistent") is False

    def test_clear(self):
        """清空缓存并重置计数。"""
        cache = TemplateCache()
        env = _make_env()
        cache.set("k1", env.from_string("x"))
        cache.get("k1")
        cache.clear()
        assert cache.size == 0
        assert cache.hits == 0
        assert cache.misses == 0

    def test_size_property(self):
        """size 属性反映当前条目数。"""
        cache = TemplateCache()
        assert cache.size == 0
        env = _make_env()
        cache.set("a", env.from_string("a"))
        assert cache.size == 1


# ---------------------------------------------------------------------------
# TemplateEngine -- 文件模板测试
# ---------------------------------------------------------------------------


class TestTemplateEngineRender:
    """文件模板渲染测试。"""

    @pytest.fixture()
    def engine(self, tmp_path: Path) -> TemplateEngine:
        """创建指向临时目录的模板引擎。"""
        tpl_dir = tmp_path / "templates"
        tpl_dir.mkdir()
        (tpl_dir / "hello.html").write_text(
            "<p>Hello, {{ name }}!</p>", encoding="utf-8"
        )
        (tpl_dir / "loop.html").write_text(
            "{% for item in items %}<li>{{ item }}</li>{% endfor %}",
            encoding="utf-8",
        )
        return TemplateEngine(template_dir=str(tpl_dir))

    def test_render_basic(self, engine: TemplateEngine):
        """基础变量替换。"""
        result = engine.render("hello.html", {"name": "CityFlow"})
        assert "Hello, CityFlow!" in result

    def test_render_loop(self, engine: TemplateEngine):
        """循环渲染。"""
        result = engine.render("loop.html", {"items": ["A", "B", "C"]})
        assert "<li>A</li>" in result
        assert "<li>B</li>" in result
        assert "<li>C</li>" in result

    def test_render_missing_template(self, engine: TemplateEngine):
        """模板不存在时抛出 TemplateRenderError。"""
        with pytest.raises(TemplateRenderError, match="模板文件不存在"):
            engine.render("no_such_template.html")

    def test_render_no_context(self, engine: TemplateEngine):
        """不传 context 时使用空字典。"""
        (engine.template_dir / "static.html").write_text(
            "static content", encoding="utf-8"
        )
        result = engine.render("static.html")
        assert result == "static content"


# ---------------------------------------------------------------------------
# TemplateEngine -- 字符串模板测试
# ---------------------------------------------------------------------------


class TestTemplateEngineRenderString:
    """字符串模板渲染测试。"""

    @pytest.fixture()
    def engine(self, tmp_path: Path) -> TemplateEngine:
        return TemplateEngine(template_dir=str(tmp_path))

    def test_render_string_basic(self, engine: TemplateEngine):
        """基础字符串渲染。"""
        result = engine.render_string("Hi {{ x }}", {"x": 42})
        assert result == "Hi 42"

    def test_render_string_no_context(self, engine: TemplateEngine):
        """无上下文时返回原文。"""
        result = engine.render_string("no vars here")
        assert result == "no vars here"

    def test_render_string_caches(self, engine: TemplateEngine):
        """相同字符串模板命中缓存。"""
        tpl = "cached {{ v }}"
        engine.render_string(tpl, {"v": 1})
        engine.render_string(tpl, {"v": 2})
        assert engine.string_cache.hits == 1
        assert engine.string_cache.misses == 1


# ---------------------------------------------------------------------------
# TemplateEngine -- 缓存行为测试
# ---------------------------------------------------------------------------


class TestTemplateEngineCache:
    """文件模板缓存行为测试。"""

    def test_file_template_cached(self, tmp_path: Path):
        """重复渲染同一文件模板命中缓存。"""
        tpl_dir = tmp_path / "tpl"
        tpl_dir.mkdir()
        (tpl_dir / "a.html").write_text("{{ x }}", encoding="utf-8")

        engine = TemplateEngine(template_dir=str(tpl_dir))
        engine.render("a.html", {"x": 1})
        engine.render("a.html", {"x": 2})

        assert engine.cache.hits == 1
        assert engine.cache.misses == 1

    def test_file_mtime_change_invalidates_cache(self, tmp_path: Path):
        """文件修改后缓存自动失效。"""
        import time as _time

        tpl_dir = tmp_path / "tpl"
        tpl_dir.mkdir()
        tpl_file = tpl_dir / "a.html"
        tpl_file.write_text("v1={{ x }}", encoding="utf-8")

        engine = TemplateEngine(template_dir=str(tpl_dir))
        r1 = engine.render("a.html", {"x": "old"})
        assert "v1=old" in r1

        # 修改文件内容
        _time.sleep(0.05)
        tpl_file.write_text("v2={{ x }}", encoding="utf-8")

        r2 = engine.render("a.html", {"x": "new"})
        assert "v2=new" in r2

    def test_invalidate_cache(self, tmp_path: Path):
        """手动清空缓存。"""
        tpl_dir = tmp_path / "tpl"
        tpl_dir.mkdir()
        (tpl_dir / "a.html").write_text("{{ x }}", encoding="utf-8")

        engine = TemplateEngine(template_dir=str(tpl_dir))
        engine.render("a.html", {"x": 1})
        assert engine.cache.size == 1

        engine.invalidate_cache()
        assert engine.cache.size == 0
        assert engine.string_cache.size == 0


# ---------------------------------------------------------------------------
# TemplateEngine -- 过滤器和全局变量
# ---------------------------------------------------------------------------


class TestTemplateEngineExtensions:
    """自定义过滤器和全局变量测试。"""

    @pytest.fixture()
    def engine(self, tmp_path: Path) -> TemplateEngine:
        return TemplateEngine(template_dir=str(tmp_path))

    def test_custom_filter(self, engine: TemplateEngine):
        """自定义过滤器生效。"""
        engine.add_filter("shout", lambda s: s.upper() + "!")
        result = engine.render_string("{{ msg | shout }}", {"msg": "hello"})
        assert result == "HELLO!"

    def test_custom_global(self, engine: TemplateEngine):
        """全局变量在模板中可用。"""
        engine.add_global("site_name", "CityFlow")
        result = engine.render_string("Welcome to {{ site_name }}")
        assert result == "Welcome to CityFlow"


# ---------------------------------------------------------------------------
# 全局单例测试
# ---------------------------------------------------------------------------


class TestGlobalSingleton:
    """全局单例函数测试。"""

    def setup_method(self) -> None:
        reset_template_engine()

    def teardown_method(self) -> None:
        reset_template_engine()

    def test_get_template_engine_returns_singleton(self):
        """get_template_engine 返回同一实例。"""
        e1 = get_template_engine()
        e2 = get_template_engine()
        assert e1 is e2

    def test_reset_template_engine(self):
        """reset 后重新创建。"""
        e1 = get_template_engine()
        reset_template_engine()
        e2 = get_template_engine()
        assert e1 is not e2

    def test_render_string_convenience(self):
        """render_string 便捷函数可用。"""
        result = render_string("{{ a }}+{{ b }}", {"a": 1, "b": 2})
        assert result == "1+2"


# ---------------------------------------------------------------------------
# route_narrative.html 集成测试
# ---------------------------------------------------------------------------


class TestRouteNarrativeTemplate:
    """route_narrative.html 模板集成测试。"""

    @pytest.fixture()
    def engine(self) -> TemplateEngine:
        """使用项目根目录的 templates 目录。"""
        project_root = Path(__file__).resolve().parent.parent
        tpl_dir = project_root / "templates"
        if not (tpl_dir / "route_narrative.html").exists():
            pytest.skip("route_narrative.html 模板不存在")
        return TemplateEngine(template_dir=str(tpl_dir))

    def test_full_render(self, engine: TemplateEngine):
        """完整路线数据渲染。"""
        context = {
            "title": "周末出行计划",
            "opening": "给自己一个放松的周末。",
            "steps": [
                {
                    "poi": {"name": "故宫博物院"},
                    "arrival_time": "09:00",
                    "departure_time": "11:00",
                    "narrative": "感受历史的厚重。",
                },
                {
                    "poi": {"name": "南锣鼓巷"},
                    "arrival_time": "11:30",
                    "departure_time": "13:00",
                    "narrative": "逛胡同、吃小吃。",
                },
            ],
            "closing": "今天的行程就到这里，希望你喜欢。",
            "emotion_highlights": [
                {
                    "poi": "故宫博物院",
                    "description": "文化底蕴深厚",
                }
            ],
        }
        result = engine.render("route_narrative.html", context)

        assert "周末出行计划" in result
        assert "故宫博物院" in result
        assert "南锣鼓巷" in result
        assert "09:00" in result
        assert "11:00" in result
        assert "感受历史的厚重" in result
        assert "今天的行程就到这里" in result
        assert "亮点时刻" in result
        assert "文化底蕴深厚" in result

    def test_minimal_render(self, engine: TemplateEngine):
        """最少数据渲染不报错。"""
        context: dict = {"steps": []}
        result = engine.render("route_narrative.html", context)
        assert "<html" in result
        assert "路线详情" in result


# ---------------------------------------------------------------------------
# TemplateRenderError 测试
# ---------------------------------------------------------------------------


class TestTemplateRenderError:
    """异常类测试。"""

    def test_default_message(self):
        exc = TemplateRenderError()
        assert exc.code.value == 3004
        assert "模板渲染失败" in exc.message

    def test_custom_message_with_details(self):
        exc = TemplateRenderError(
            message="自定义错误",
            details={"template": "bad.html"},
        )
        assert exc.message == "自定义错误"
        assert exc.details["template"] == "bad.html"

    def test_to_dict(self):
        exc = TemplateRenderError(message="err", details={"k": "v"})
        d = exc.to_dict()
        assert d["error"]["code"] == 3004
        assert d["error"]["message"] == "err"
        assert d["error"]["details"]["k"] == "v"


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


def _make_env() -> Environment:
    """创建一个简单的 Jinja2 Environment（无文件加载器）。"""
    return Environment()
