"""CityFlow 性能基准测试模块。

模块结构：
    metrics        -- 性能指标定义与阈值配置
    baseline       -- 基准测试核心运行器（单场景）
    suite          -- 基准测试套件（多场景聚合 + 报告生成）
    run_benchmark  -- 命令行基准测试脚本（单场景入口）
    run_suite      -- 命令行基准测试套件脚本（多场景入口）
    stress_test      -- 压力测试（并发/长时间/峰值）
    stress_optimizer -- 优化压力测试引擎（渐进式加压/端点分组统计）
    locustfile       -- Locust 压力测试配置

运行基准测试::

    # 单场景模式
    python -m backend.benchmarks.run_benchmark
    python -m backend.benchmarks.run_benchmark --iterations 200 --concurrency 10

    # 套件模式（多场景 + JSON 报告）
    python -m backend.benchmarks.run_suite
    python -m backend.benchmarks.run_suite --iterations 200 --concurrency 5
    python -m backend.benchmarks.run_suite --only health,poi --output report.json

运行优化压力测试::

    python -m backend.benchmarks.run_stress_optimized
    python -m backend.benchmarks.run_stress_optimized --test progressive --max-users 200
    python -m backend.benchmarks.run_stress_optimized --test endurance --endurance-minutes 10
"""
