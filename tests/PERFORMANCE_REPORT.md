# CityFlow Performance Test Report

Generated: 2026-05-09

## Test Environment

- Python 3.12.7
- FastAPI (ASGI transport, in-process testing)
- 3689 POIs in database
- No external LLM calls (rule-based fallback used)

---

## 1. API Response Time Summary

| Endpoint | Avg (ms) | Median (ms) | P95 (ms) | P99 (ms) | Stdev (ms) | Requests | Errors |
|---|---|---|---|---|---|---|---|
| GET /api/health | 0.49 | 0.38 | 0.70 | 3.51 | 0.47 | 50 | 0 |
| POST /api/poi/search | 58.55 | 6.02 | 294.86 | 294.86 | 88.55 | 20 | 0 |
| GET /api/poi/detail/{id} | 0.59 | 0.52 | 0.88 | 0.88 | 0.14 | 20 | 0 |
| POST /api/poi/distance-matrix | 1.37 | 1.21 | 2.70 | 2.70 | 0.47 | 10 | 0 |
| GET /api/data/ (all) | 100.12 | 73.01 | 438.65 | 438.65 | 83.80 | 20 | 0 |
| GET /api/datasets | 0.29 | 0.27 | 0.47 | 0.47 | 0.05 | 20 | 0 |
| GET /api/poi/?city=X | 59.81 | 58.43 | 69.53 | 69.53 | 5.72 | 20 | 0 |
| GET /api/order/?city=X&hour=Y | 30.35 | 29.48 | 36.10 | 36.10 | 2.87 | 20 | 0 |
| GET /api/road-traffic/?city=X&hour=Y | 0.91 | 0.82 | 1.60 | 1.60 | 0.25 | 20 | 0 |
| POST /api/plan (SSE, full) | 7192.18 | 8001.06 | 8011.15 | 8011.15 | 1409.78 | 3 | 0 |
| POST /api/plan (first event) | 7192.06 | 8000.95 | 8011.05 | 8011.05 | 1409.79 | 3 | 0 |

### Key Findings

- Health check is extremely fast: sub-millisecond average.
- POI detail is very fast: ~0.6ms average.
- Distance matrix with 10 POIs: ~1.4ms average (numpy vectorized).
- POI search has high variance (6ms median vs 295ms max) due to first-request cold start.
- Data endpoints (`/api/data/`, `/api/poi/`) are slower (~60-100ms) because they serialize large result sets (3689 items).
- Route planning (SSE) takes 5.5-8 seconds per request, dominated by LLM intent parsing timeout (5s) and solver execution.

---

## 2. Concurrency Test Results

| Test | Concurrent | Success | Throughput | Duration |
|---|---|---|---|---|
| Health check | 100 | 100/100 | 3257.2 req/s | 0.031s |
| POI search | 30 | 30/30 | 35.0 req/s | 0.856s |
| Mixed (50 health + 30 search + 20 data) | 100 | 100/100 | 34.5 req/s | 2.902s |

### Key Findings

- Health check handles 100 concurrent requests with zero errors at 3257 req/s.
- POI search handles 30 concurrent at 35 req/s -- the bottleneck is the POI data serialization (enrich_poi for each result).
- Mixed workload runs cleanly with 100% success rate.
- The system is I/O-bound on data serialization, not on request handling.

---

## 3. Memory Leak Detection

| Metric | Value |
|---|---|
| Initial memory | 193.4 MB |
| Final memory (after 100 rounds) | 194.1 MB |
| Memory increase | 0.6 MB |
| Sampling points | [193.4, 193.4, 193.4, 193.4, 193.4] MB |

Result: No memory leak detected. Memory usage is stable.

---

## 4. Cache Effectiveness

| Metric | Value |
|---|---|
| Cold request avg (no cache) | 1.38 ms |
| Hot request avg (cached) | 1.31 ms |
| Speedup ratio | 1.1x |

Note: Distance matrix cache shows minimal speedup because the numpy computation itself is very fast (~1ms for 10 POIs). Cache overhead (dict lookup, key hashing) nearly equals computation time at this scale. Cache becomes more valuable with larger matrices or repeated identical requests.

---

## 5. Search Scalability (Data Volume vs Response Time)

| Filter | Response Time | Result Count |
|---|---|---|
| No filter (all data) | 399.58 ms | 3689 |
| City filter | 93.36 ms | 999 |
| Category filter | 14.80 ms | 145 |
| Composite filter | 3.96 ms | 30 |
| Keyword search | 2.73 ms | 10 |

### Key Finding

Response time scales linearly with result count. The main cost is `enrich_poi()` being called on every result (adds emotion_tags, constraints, price_range). Returning all 3689 POIs takes ~400ms.

---

## 6. Route Planning (SSE) Deep Dive

The `/api/plan` endpoint is the heaviest:

| Phase | Duration |
|---|---|
| Intent parsing (LLM timeout + rule fallback) | ~5.0s |
| Candidate search + filter | ~0.1s |
| Route solving (TSPTW) | ~1.5s |
| Narrative generation | ~0.5s |
| **Total** | **~7.2s** |

The 5-second LLM timeout is the dominant cost. When the LLM is available, this should drop to ~2-3s.

---

## 7. Identified Bottlenecks & Optimization Recommendations

### Bottleneck 1: POI Search Serialization (HIGH PRIORITY)

Problem: `enrich_poi()` is called on every search result, adding default emotion_tags and constraints to POIs that lack them. For 3689 POIs, this adds ~400ms.

Recommendation:
- Pre-compute enriched data at load time (in `load_pois()`), not at query time.
- Use lazy serialization: only enrich fields the client actually requests.

### Bottleneck 2: /api/data/ Returns All Data (MEDIUM PRIORITY)

Problem: `GET /api/data/` without filters returns all 3712 records, serialized to JSON.

Recommendation:
- Add mandatory pagination (limit/offset) with a default page size of 100.
- Add `fields` parameter to return only needed columns.

### Bottleneck 3: LLM Intent Parsing Timeout (MEDIUM PRIORITY)

Problem: Intent parsing waits 5 seconds for LLM response before falling back to rules.

Recommendation:
- Implement a faster LLM model or reduce timeout to 2-3 seconds.
- Cache intent parsing results for similar inputs.
- Use the rule-based parser as the primary path, LLM as optional enhancement.

### Bottleneck 4: Route Solver is Synchronous (LOW PRIORITY)

Problem: `solve_route()` runs in `asyncio.to_thread()`, which is correct but adds thread pool overhead.

Recommendation:
- For production, consider a dedicated process pool with `ProcessPoolExecutor`.
- Profile the solver with cProfile to find internal bottlenecks.

### Bottleneck 5: No Response Compression (LOW PRIORITY)

Problem: Large JSON responses (POI lists, route results) are not compressed.

Recommendation:
- Enable gzip/brotli middleware in FastAPI.
- Typical 60-80% size reduction for JSON payloads.

### Bottleneck 6: Static File Mount Position (FIXED)

Problem: `app.mount("/", StaticFiles(...))` was placed before app-level routes, causing 404 for `/api/health` and other directly-defined routes.

Fix: Moved static mount to end of file (already applied).

---

## 8. Stress Test (Locust)

A Locust pressure test configuration is available at `tests/locustfile.py`.

To run against a live server:

```bash
# Start the server first
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Run Locust with Web UI
locust -f tests/locustfile.py --host=http://localhost:8000

# Or headless mode (50 users, 10 ramp-up, 60 seconds)
locust -f tests/locustfile.py --host=http://localhost:8000 \
    --headless -u 50 -r 10 --run-time 60s
```

---

## 9. Summary

| Metric | Status |
|---|---|
| Health check latency | Excellent (<1ms) |
| POI detail latency | Excellent (<1ms) |
| POI search latency | Good (6ms median, needs cold-start fix) |
| Distance matrix latency | Excellent (<2ms) |
| Route planning latency | Acceptable (7s, dominated by LLM timeout) |
| Concurrent handling | Good (100 concurrent, zero errors) |
| Memory stability | No leak detected |
| Search scalability | Linear with result count, needs pagination |

Overall: The system performs well for moderate load. The main optimization opportunities are pre-enriching POI data at load time and adding pagination to bulk data endpoints.
