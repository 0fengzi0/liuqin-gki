#!/usr/bin/env python3
"""Verify a rebuilt GKI kernel against the liuqin device module baseline.

Compares every symbol CRC that the device's 353 vendor modules expect
(baseline/symbol-crcs.json, extracted from the modules' __versions sections)
against the Module.symvers produced by the kernel build:

- symbol present in Module.symvers with the expected CRC  -> pass
- symbol absent from Module.symvers but exported by some
  vendor module (module-to-module dependency)             -> provided, pass
- symbol absent and not vendor-provided                    -> MISSING, fail
- CRC differs                                              -> MISMATCH, fail

The kernel uses CONFIG_MODVERSIONS: at module load the release prefix of
vermagic is ignored and these CRCs are the actual compatibility contract.

Usage:
  check-kmi.py MODULE_SYMVERS BASELINE_JSON --report kmi-report.json
"""

import argparse
import json
import sys
from pathlib import Path


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(2)


def parse_symvers(path):
    """Line layout: <crc>\t<symbol>\t<vmlinux-or-module>\t<export type>\t<namespace>."""
    crcs, namespaces = {}, {}
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1]:
            crcs[parts[1]] = parts[0].strip()
            if len(parts) >= 5:
                namespaces[parts[1]] = parts[4].strip()
    return crcs, namespaces


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("symvers", help="kernel build Module.symvers")
    ap.add_argument("baseline", help="baseline/symbol-crcs.json from the device modules")
    ap.add_argument("--report", required=True, help="output report JSON path")
    args = ap.parse_args()

    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    conflicts = baseline.get("symbolConflicts", {})
    if conflicts:
        fail(f"baseline itself has {len(conflicts)} CRC conflicts; "
             "modules disagree with each other, investigate before building")

    kernel_crcs, namespaces = parse_symvers(args.symvers)
    providers = baseline.get("providers", {})

    matched, mismatches, missing, provided, namespaced = [], [], [], [], []
    for sym, crc in sorted(baseline["symbols"].items()):
        expected = "0x" + crc.lower()
        if sym in kernel_crcs:
            if kernel_crcs[sym].lower() == expected:
                matched.append(sym)
                ns = namespaces.get(sym, "")
                if ns:
                    namespaced.append({"symbol": sym, "namespace": ns})
            else:
                mismatches.append({"symbol": sym, "expected": expected,
                                   "kernel": kernel_crcs[sym]})
        elif sym in providers:
            provided.append(sym)
        else:
            missing.append(sym)

    unused = sorted(set(kernel_crcs) - set(baseline["symbols"]))
    ok = not mismatches and not missing
    report = {
        "result": "pass" if ok else "fail",
        "baselineModules": baseline.get("moduleCount"),
        "baselineSymbols": len(baseline["symbols"]),
        "kernelSymbols": len(kernel_crcs),
        "matched": len(matched),
        "vendorProvided": len(provided),
        "mismatches": mismatches,
        "missing": missing,
        "namespacedImports": namespaced,
        "kernelSymbolsOutsideBaseline": len(unused),
        "note": "vermagic release prefix is ignored by the kernel when "
                "CONFIG_MODVERSIONS=y; these CRCs are the load contract. "
                "kernelsu.ko has no versioned imports (unversioned symbol "
                "existence only).",
    }
    Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"KMI check: {len(matched)} matched, {len(provided)} vendor-provided, "
          f"{len(mismatches)} mismatched, {len(missing)} missing, "
          f"{len(namespaced)} namespaced")
    for m in mismatches[:20]:
        print(f"  MISMATCH {m['symbol']}: baseline {m['expected']} "
              f"kernel {m['kernel']}")
    for s in missing[:20]:
        print(f"  MISSING {s}")
    if len(namespaced):
        print(f"  note: {len(namespaced)} symbols are namespace-exported; "
              "vendor modules do not record namespaces in __versions")
    print(f"report -> {args.report}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
