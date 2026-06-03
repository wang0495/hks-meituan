"""一键跑完所有未完成的基线: single_llm(100) + rag(100)"""
import subprocess, sys
from pathlib import Path

project = Path(__file__).resolve().parent
python = sys.executable

print("=" * 60)
print("  Step 1/2: Single-LLM baseline (100 scenes)")
print("=" * 60)
r1 = subprocess.run(
    [python, "-u", "-m", "scripts.benchmarks.test_baselines", "--method", "single_llm"],
    cwd=str(project), capture_output=False, text=True,
)
print(f"single_llm exit code: {r1.returncode}")

print()
print("=" * 60)
print("  Step 2/2: RAG baseline (100 scenes)")
print("=" * 60)
r2 = subprocess.run(
    [python, "-u", "-m", "scripts.benchmarks.test_baselines", "--method", "rag"],
    cwd=str(project), capture_output=False, text=True,
)
print(f"rag exit code: {r2.returncode}")

print()
print("=" * 60)
if r1.returncode == 0 and r2.returncode == 0:
    print("  ALL BASELINES COMPLETE!")
else:
    print(f"  Done with issues: single_llm={r1.returncode}, rag={r2.returncode}")
print("=" * 60)
