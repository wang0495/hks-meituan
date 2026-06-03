# CityFlow Project Memory

## Project Overview
- Paper: CityFlow - Multi-agent LLM route planning system for Zhuhai tourism
- Primary target: IEEE Access (SCI Q2, IF 3.4, free submit, $1995 APC if accepted)
- Fallback: 计算机工程 (requires Word format, not LaTeX)
- POI database: 2129 entries, Zhuhai only (NO Guangzhou data)
- LLM: iFlytek xopqwen35v35b via API (base URL in .env as LLM_BASE_URL)
- Evaluation: LLM-as-Judge 7-dimension scoring (0-100 scale)

## Key Technical Notes
- .env uses LLM_BASE_URL / LLM_API_KEY (not XUNFEI_BASE / XUNFEI_API_KEY)
- test_baselines.py reads env vars with fallback: XUNFEI_BASE → XUNFEI_BASE_URL → LLM_BASE_URL
- API URL construction: if '/v2' or '/v1' in base_url → append '/chat/completions'
- Each LLM call ~6-13s; with 1.5s delay = ~8-15s/scenario for single_llm
- 讯飞 API has 429 rate limiting; retry with exponential backoff
- Greedy baseline: all 100 scenarios score 100 (no discrimination in simplified scoring)
- Greedy routes are non-personalized: all same-type scenarios return identical stops

## Paper Status (2026-06-03, FINAL)
- 27 references (meets ≥25 requirement)
- All \cite/\bibitem and \ref/\label cross-verified, zero orphans
- No TODO/FIXME/XXX remaining
- Guangzhou references fully removed
- Experiments: 16 subsections (added Baseline Comparison with 4 methods)
- **Baseline comparison**: Greedy vs Single-LLM vs Single-LLM+RAG vs CityFlow (tab:baseline_compare)
- **Chinese version (计算机工程)**: paper/cityflow_paper.docx (51KB)
- **IEEE Access version (SCI)**: paper/ieee_access/ (IEEEtran class, pure English, 27 IEEE-format refs)
  - paper/ieee_access.zip → upload to Overleaf for one-click PDF compilation
  - Target: IEEE Access, SCI Q2, IF 3.4, ~$1995 APC (only if accepted)
  - User strategy: try IEEE Access first (free to submit), fallback to 计算机工程 (Word)
- **PAPER IS READY FOR SUBMISSION (both versions)**
- **PDF compiled**: paper/ieee_access/main.pdf (12 pages, 288KB, zero warnings)
- **Tools installed**: MiKTeX 25.12, pandoc 3.6

## Baseline Results Summary (100 scenarios, ALL COMPLETE)
- **Greedy**: pass 100%, score 100.0, hallucination 0%, diversity 1/20 per type (identical routes), avg 8.0 stops
- **Single-LLM**: pass 100%, score 66.9, hallucination 22.1%, diversity 20/20 per type, avg 5.3 stops
- **Single-LLM+RAG**: pass 99%, score 83.8, hallucination 0%, diversity 15-18/20, avg 5.0 stops
- **CityFlow**: pass 90%, score 74.3 (LLM-Judge), hallucination 0%, diversity 20/20 per type
- Key insight: RAG eliminates hallucination (0%) and achieves highest simplified score (83.8), but CityFlow delivers full diversity + LLM-as-Judge quality assessment
- hallucination check: fuzzy substring match against 1901 real POIs in city_poi_db.json

## Known Issues
- Simplified rule-based scoring has no discrimination for greedy (all 100)
- LLM-as-Judge scores (CityFlow 74.3) are NOT directly comparable to simplified scores (paper includes footnote)
- CityFlow 10% fail: time-constrained scenarios where route gets truncated below 3 stops
