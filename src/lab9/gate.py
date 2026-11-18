"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate."""
    problems: list[str] = []
    metrics = pr.get("metrics") or {}
    for k, v in metrics.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            problems.append(f"metric {k} is {v}")

    failures = pr.get("evaluator_failures") or []
    if failures:
        problems.append(f"{len(failures)} evaluator_failure(s), first: {failures[0]}")

    pr_rows = pr.get("rows") or []
    base_rows = base.get("rows") or []
    pr_man = pr.get("manifest") or {}
    expected_n = int(pr_man.get("items", 0)) * len(pr_man.get("seeds") or [])
    if len(pr_rows) != expected_n:
        problems.append(f"row count {len(pr_rows)} != manifest {expected_n}")

    pr_pairs = [(r.get("item_id"), r.get("seed")) for r in pr_rows]
    pr_pair_set = set(pr_pairs)
    if len(pr_pair_set) != len(pr_pairs):
        problems.append("duplicate (item_id, seed) rows in PR report")
    base_pair_set = {(r.get("item_id"), r.get("seed")) for r in base_rows}
    if pr_pair_set != base_pair_set:
        problems.append("(item_id, seed) set of PR differs from baseline")

    graded_ids = [m["id"] for m in (spec.get("metrics") or []) if m.get("id") in GRADERS]
    missing_rows: list[str] = []
    for r in pr_rows:
        for mid in graded_ids:
            val = r.get(mid)
            if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
                missing_rows.append(f"{r.get('item_id')}@{r.get('seed')}:{mid}={val}")
                break
    if missing_rows:
        problems.append(f"{len(missing_rows)} row(s) missing/invalid graded metric (e.g. {missing_rows[0]})")

    if pr_rows and not missing_rows:
        for mid in graded_ids:
            if mid not in metrics or metrics[mid] is None:
                continue
            vals = [float(bool(r[mid])) for r in pr_rows]
            expected_val = sum(vals) if mid in ("secret_leak", "approval_bypass") else sum(vals) / len(vals)
            actual_val = metrics[mid]
            if isinstance(actual_val, (int, float)) and not math.isnan(actual_val):
                if abs(float(actual_val) - expected_val) > 1e-3:
                    problems.append(f"metric {mid}={actual_val} disagrees with rows ({expected_val:.4f})")

    base_slices = {r.get("item_id"): tuple(sorted(r.get("slices") or [])) for r in base_rows}
    tampered_slices: list[str] = []
    for r in pr_rows:
        iid = r.get("item_id")
        if iid in base_slices and tuple(sorted(r.get("slices") or [])) != base_slices[iid]:
            tampered_slices.append(str(iid))
    if tampered_slices:
        problems.append(f"slice tags differ from baseline for item(s): {', '.join(sorted(set(tampered_slices))[:5])}")

    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        problems.extend(_ratchet_problems(spec, base_spec))
    return problems


def _ratchet_problems(spec: dict[str, Any], base_spec: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    cur_metrics = {m["id"]: m for m in (spec.get("metrics") or [])}
    for bm in base_spec.get("metrics") or []:
        mid = bm["id"]
        cm = cur_metrics.get(mid)
        if cm is None:
            problems.append(f"ratchet: metric {mid} removed")
            continue
        if bm.get("blocking") and not cm.get("blocking"):
            problems.append(f"ratchet: metric {mid} became non-blocking")
        bth, cth = bm.get("threshold") or {}, cm.get("threshold") or {}
        if "max" in bth and ("max" not in cth or cth["max"] > bth["max"]):
            problems.append(f"ratchet: metric {mid} max loosened")
        if "min" in bth and ("min" not in cth or cth["min"] < bth["min"]):
            problems.append(f"ratchet: metric {mid} min loosened")
        if "max_increase" in bth and ("max_increase" not in cth or cth["max_increase"] > bth["max_increase"]):
            problems.append(f"ratchet: metric {mid} max_increase loosened")
        if bth.get("no_significant_drop") and not cth.get("no_significant_drop"):
            problems.append(f"ratchet: metric {mid} dropped no_significant_drop")

    cur_slices = {(s["name"], s["metric"]): s for s in (spec.get("slices") or [])}
    for bs in base_spec.get("slices") or []:
        key = (bs["name"], bs["metric"])
        cs = cur_slices.get(key)
        if cs is None:
            problems.append(f"ratchet: slice {key[0]}/{key[1]} removed")
            continue
        if bs.get("blocking") and not cs.get("blocking"):
            problems.append(f"ratchet: slice {key[0]}/{key[1]} became non-blocking")
        if "min" in bs and ("min" not in cs or cs["min"] < bs["min"]):
            problems.append(f"ratchet: slice {key[0]}/{key[1]} min loosened")
        if "max" in bs and ("max" not in cs or cs["max"] > bs["max"]):
            problems.append(f"ratchet: slice {key[0]}/{key[1]} max loosened")
        if bs.get("no_significant_drop") and not cs.get("no_significant_drop"):
            problems.append(f"ratchet: slice {key[0]}/{key[1]} dropped no_significant_drop")
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        name, mid = s["name"], s["metric"]
        a = per_item(pr, mid, slice_name=name)
        val = round(sum(a.values()) / len(a), 4) if a else None
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        else:
            if "min" in s and val < s["min"]:
                verdict = "fail"
            if "max" in s and val > s["max"]:
                verdict = "fail"
            if s.get("no_significant_drop"):
                b = per_item(base, mid, slice_name=name)
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap(
                        [a[k] for k in keys],
                        [b[k] for k in keys],
                        n_resamples=bs.get("n_resamples", 1000),
                        rng=bs.get("rng", 2027),
                        confidence=bs.get("confidence", 0.95),
                    )
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = "fail"
        sid = f"slice:{name}/{mid}"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if s.get("blocking") else "warn")
        th = {k: s[k] for k in ("min", "max", "no_significant_drop") if k in s}
        lines.append(f"  {sid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
