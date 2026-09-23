"""
Recompute every figure in the README from the CSVs in data/.

Usage: python scripts/analyze.py
"""
import csv, pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent

def load(name):
    with open(ROOT / "data" / name, newline="") as fh:
        return list(csv.DictReader(fh))

def main():
    by_asset = load("corpus_by_asset.csv")
    ts = load("corpus_timeseries.csv")

    counts = {r["asset"]: int(r["addresses_listed"]) for r in by_asset}
    total = sum(counts.values())
    top4 = sum(sorted(counts.values(), reverse=True)[:4])
    singles = [a for a, c in counts.items() if c == 1]

    print(f"Assets covered          : {len(counts)}")
    print(f"Address listings        : {total}")
    print(f"Top 4 assets            : {top4} ({top4/total*100:.1f}%)")
    print(f"Assets with 1 address   : {len(singles)} ({', '.join(sorted(singles))})")

    series = defaultdict(list)
    for r in ts:
        series[r["asset"]].append((r["date"], int(r["addresses_listed"])))
    for a in series:
        series[a].sort()

    dates = sorted({d for s in series.values() for d, _ in s})
    state, totals = {a: 0 for a in series}, []
    for d in dates:
        for a, s in series.items():
            for dd, c in s:
                if dd == d:
                    state[a] = c
        totals.append((d, sum(state.values())))

    deltas = [(d, t - p) for (d, t), (_, p) in zip(totals[1:], totals[:-1])]
    adds = [x for x in deltas if x[1] > 0]
    drops = [x for x in deltas if x[1] < 0]
    top5 = sorted(adds, key=lambda x: -x[1])[:5]

    print(f"Revisions observed      : {len(ts)} across {len(dates)} dates")
    print(f"Corpus {totals[0][0]}     : {totals[0][1]}")
    print(f"Corpus {totals[-1][0]}     : {totals[-1][1]}")
    print(f"Net decreases           : {len(drops)} -> {drops}")
    print(f"Largest addition        : {max(adds, key=lambda x: x[1])}")
    print(f"Top 5 dates share       : {sum(x[1] for x in top5)/sum(x[1] for x in adds)*100:.1f}% of all additions")

    eth = series["ETH"]
    peak = max(eth, key=lambda x: x[1])
    after = [c for d, c in eth if d > peak[0]]
    if after:
        print(f"ETH peak / next obs     : {peak[1]} -> {after[0]} ({(peak[1]-after[0])/peak[1]*100:.0f}% removed)")

if __name__ == "__main__":
    main()
