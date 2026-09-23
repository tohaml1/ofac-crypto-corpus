"""
Screen a transaction file against the OFAC digital currency address list.

The point of this script is the second check. Matching an address against the
list is trivial. The interesting failure is that the list is asset-scoped and
EVM addresses are not: the same key controls the same address on Ethereum,
Arbitrum, BNB Chain, Base, Polygon and everywhere else, whether or not the
designation named those chains.

A screening rule of "address AND asset must both match" therefore passes
transactions that a rule of "address matches" would stop.

Usage:
  python screen.py transactions.csv sanctioned_addresses.csv

transactions.csv : any CSV containing an address column and an asset column
                   (names auto-detected, or set with --address / --asset)
sanctioned_addresses.csv : address,asset

Output: screening_hits.csv, one row per hit, with the match type.
"""

import argparse
import csv
import sys

EVM_ASSETS = {"ETH", "ARB", "BSC", "ETC", "USDT", "USDC", "BASE", "MATIC", "OP", "AVAX"}

ADDRESS_COLS = ["address", "to", "to_address", "counterparty", "destination", "wallet"]
ASSET_COLS = ["asset", "token", "currency", "coin", "chain", "symbol"]


def pick(header, explicit, candidates, label):
    if explicit:
        if explicit not in header:
            sys.exit(f"column '{explicit}' not in file. Columns: {header}")
        return explicit
    lower = {h.lower(): h for h in header}
    for c in candidates:
        if c in lower:
            return lower[c]
    sys.exit(f"could not find a {label} column. Columns: {header}")


def is_evm(address):
    return address.startswith("0x") and len(address) == 42


def load_list(path):
    exact, by_address = set(), {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            addr = row["address"].strip().lower()
            asset = row["asset"].strip().upper()
            exact.add((addr, asset))
            by_address.setdefault(addr, set()).add(asset)
    return exact, by_address


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transactions_csv")
    ap.add_argument("sanctioned_csv")
    ap.add_argument("--address")
    ap.add_argument("--asset")
    args = ap.parse_args()

    exact, by_address = load_list(args.sanctioned_csv)

    with open(args.transactions_csv, newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        addr_col = pick(header, args.address, ADDRESS_COLS, "address")
        asset_col = pick(header, args.asset, ASSET_COLS, "asset")
        rows = list(reader)

    hits = []
    for i, row in enumerate(rows, start=2):
        addr = str(row[addr_col]).strip().lower()
        asset = str(row[asset_col]).strip().upper()
        if not addr:
            continue

        if (addr, asset) in exact:
            kind = "EXACT"
            note = "address and asset both listed"
        elif addr in by_address:
            listed = sorted(by_address[addr])
            if is_evm(addr) and asset in EVM_ASSETS:
                kind = "CROSS_CHAIN_EVM"
                note = f"same EVM address listed under {'/'.join(listed)}; same key controls it on {asset}"
            else:
                kind = "ADDRESS_ONLY"
                note = f"address listed under {'/'.join(listed)}, not under {asset}"
        else:
            continue

        hits.append({
            "row": i, "address": addr, "asset_in_file": asset,
            "match_type": kind, "note": note,
        })

    by_kind = {}
    for h in hits:
        by_kind[h["match_type"]] = by_kind.get(h["match_type"], 0) + 1

    print(f"Transactions screened : {len(rows)}")
    print(f"Hits                  : {len(hits)}")
    for k in ("EXACT", "CROSS_CHAIN_EVM", "ADDRESS_ONLY"):
        if by_kind.get(k):
            print(f"  {k:<18} {by_kind[k]}")

    missed = by_kind.get("CROSS_CHAIN_EVM", 0) + by_kind.get("ADDRESS_ONLY", 0)
    if missed:
        print()
        print(f"{missed} of these would be missed by an address+asset matching rule.")
        print("Escalate them; do not auto-clear on the basis that the asset differs.")

    if hits:
        with open("screening_hits.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(hits[0]))
            w.writeheader()
            w.writerows(hits)
        print("\nWritten: screening_hits.csv")


if __name__ == "__main__":
    main()
