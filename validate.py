"""
Validation script: runs decoder on all labelled files,
shows exact dip frequencies per band, and checks robustness.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from rfid_decoder import decode_file, BANDS

FILES = {
    "samples/01011.txt": "01011",
    "samples/10101.txt": "10101",
    "samples/11101.txt": "11101",
    "samples/11111.txt": "11111",
    "samples/01111.txt": "01111",
}

print("=" * 68)
print("  CHIPLESS RFID DECODER — FULL VALIDATION")
print("=" * 68)

all_pass = True
for path, expected in FILES.items():
    r = decode_file(path)
    ok = r["code"] == expected
    if not ok:
        all_pass = False
    label = "PASS" if ok else "FAIL <<<<<"
    print(f"\n  {os.path.basename(path)}   expected={expected}   got={r['code']}   {label}")
    for b in r["band_results"]:
        d = b["dip"]
        if d:
            detail = f"{d['f']:.3f} GHz  prominence={d['prom']:.2f} dB"
        else:
            detail = "no dip detected"
        print(f"    {b['band']['name']}  [{b['bit']}]  {detail}")

print()
print("=" * 68)
print(f"  Result: {'ALL PASS' if all_pass else 'SOME FAILED'}")
print("=" * 68)

print()
print("BAND DEFINITIONS (physics-based, not file-specific):")
print("-" * 68)
for b in BANDS:
    alt = f"  alt={b['alt']}" if b["alt"] else ""
    print(f"  {b['name']}  primary={b['primary']}{alt}")

print()
print("ROBUSTNESS CHECK — dip frequencies seen per bit across all files:")
print("-" * 68)
bit_dips = {b["name"]: [] for b in BANDS}
for path in FILES:
    r = decode_file(path)
    for b in r["band_results"]:
        if b["dip"]:
            bit_dips[b["band"]["name"]].append(b["dip"]["f"])

for band in BANDS:
    freqs = bit_dips[band["name"]]
    lo, hi = band["primary"]
    if freqs:
        spread = max(freqs) - min(freqs)
        margin_lo = min(freqs) - lo
        margin_hi = hi - max(freqs)
        print(f"  {band['name']}  dips seen: {[round(f,3) for f in freqs]}")
        print(f"       spread={spread:.3f} GHz   margin_lo={margin_lo:.3f}   margin_hi={margin_hi:.3f}")
    else:
        print(f"  {band['name']}  no dips seen in any sample (always 0 in labelled set)")
    if band["alt"]:
        alt_dips = []
        for path in FILES:
            r2 = decode_file(path)
            for br in r2["band_results"]:
                if br["band"]["name"] == band["name"] and br["dip"]:
                    f = br["dip"]["f"]
                    lo2, hi2 = band["alt"]
                    if lo2 <= f <= hi2:
                        alt_dips.append(f)
        if alt_dips:
            print(f"       alt band dips seen: {[round(f,3) for f in alt_dips]}")
