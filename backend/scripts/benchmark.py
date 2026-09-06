"""性能基准测试：5,000 条存量数据下的关键接口 P50/P95/P99。

用法：
    python scripts/benchmark.py [--base http://localhost:8000] [--json OUT_PATH] [--samples 20]

写入口（质量检测 / 疑似错误检测）各执行 1 次并单独计时；
列表/查询接口按 --samples 次采样输出分位数。
结果末尾以 JSON 行输出，便于跨次对比（--json 落盘）。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time

import httpx

LIST_ENDPOINTS = [
    ("GET", "/api/quality-checks/rules"),
    ("GET", "/api/quality-checks/results"),
    ("GET", "/api/quality-checks/batches"),
    ("GET", "/api/quality-checks/report"),
    ("GET", "/api/suspected-errors"),
    ("GET", "/api/copilot/todos"),
    ("GET", "/api/governance/clusters"),
    ("GET", "/api/data-standards"),
    ("GET", "/api/owners"),
    ("GET", "/api/metadata/entities"),
    ("GET", "/api/metadata/fields"),
    ("GET", "/api/metadata/glossary"),
]

WRITE_ENDPOINTS = [
    ("POST", "/api/quality-checks/run", {"entity_type": "material"}),
    ("POST", "/api/suspected-errors/detect", {"entity_type": "material"}),
]


def percentile(samples: list[float], p: float) -> float:
    ordered = sorted(samples)
    idx = min(len(ordered) - 1, max(0, round(p / 100 * (len(ordered) - 1))))
    return ordered[idx]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    report: dict = {"base": args.base, "samples": args.samples, "list": {}, "write": {}}

    with httpx.Client(base_url=args.base, timeout=120.0) as client:
        resp = client.post("/api/auth/login", json={"user_id": "admin001", "password": "adminpass001"})
        resp.raise_for_status()
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        for method, path, payload in WRITE_ENDPOINTS:
            t0 = time.perf_counter()
            r = client.request(method, path, json=payload, headers=headers)
            elapsed = time.perf_counter() - t0
            ok = r.status_code < 400
            report["write"][path] = {"seconds": round(elapsed, 3), "status": r.status_code, "ok": ok}
            print(f"WRITE {path:34s} {elapsed:8.3f}s  status={r.status_code}")

        for method, path in LIST_ENDPOINTS:
            samples = []
            status = None
            for _ in range(args.samples):
                t0 = time.perf_counter()
                r = client.request(method, path, headers=headers)
                status = r.status_code
                samples.append((time.perf_counter() - t0) * 1000)
            report["list"][path] = {
                "p50_ms": round(percentile(samples, 50), 1),
                "p95_ms": round(percentile(samples, 95), 1),
                "p99_ms": round(percentile(samples, 99), 1),
                "mean_ms": round(statistics.mean(samples), 1),
                "status": status,
            }
            print(
                f"LIST  {path:34s} p50={report['list'][path]['p50_ms']:7.1f}ms "
                f"p95={report['list'][path]['p95_ms']:7.1f}ms p99={report['list'][path]['p99_ms']:7.1f}ms"
            )

    worst_p95 = max((v["p95_ms"] for v in report["list"].values()), default=0)
    slow_write = [p for p, v in report["write"].items() if not v["ok"]]
    print(f"\nWORST_LIST_P95={worst_p95}ms slow_writes={slow_write or 'none'}")
    report["worst_list_p95_ms"] = worst_p95

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"saved -> {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
