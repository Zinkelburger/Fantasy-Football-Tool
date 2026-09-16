"""Compare 18 manually transcribed screenshot rows with our saved Week 1 export.

The ftn_/pfr_ column names in the sample select our comparison fields; they
do NOT attribute the screenshot to those providers. This is a spot check,
not a complete audit of the 120 displayed rows or a model-accuracy test.
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def compare():
    with (ROOT / "data/weekly/advanced_usage_2026_weekly.csv").open() as f:
        actual = {(r["name"], r["position"]): r for r in csv.DictReader(f) if r["week"] == "1"}
    counts, differences = {}, []
    with (HERE / "screenshot-sample-2026-wk01.csv").open() as f:
        rows = list(csv.DictReader(f))
    for source in rows:
        row = actual[(source["name"], source["position"])]
        for field, expected in source.items():
            if field in ("name", "position") or expected == "":
                continue
            value = row["target_share"] if field == "target_share_pct" else row[field]
            observed = None if value == "" else float(value)
            if observed is not None and field == "target_share_pct":
                observed = int(observed * 100 + .5)
            status = "unavailable" if observed is None else "match" if observed == float(expected) else "different"
            tally = counts.setdefault(field, {"match": 0, "different": 0, "unavailable": 0})
            tally[status] += 1
            if status != "match":
                differences.append({"name": source["name"], "field": field,
                                    "screenshot": float(expected), "ours": observed, "status": status})
    return {"season": 2026, "week": 1, "sample_rows": len(rows), "counts": counts, "differences": differences}


if __name__ == "__main__":
    result = compare()
    (HERE / "screenshot-comparison-2026-wk01.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
