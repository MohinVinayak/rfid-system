"""
Chipless RFID 5-Bit CST Decoder
Input: CST Total RCS vs Frequency .txt file
Output: 5-bit binary tag code + matched inventory item

Band mapping derived from actual labelled CST simulations:
  b4  3.40 – 3.90 GHz
  b3  4.40 – 4.95 GHz
  b2  5.60 – 6.10 GHz
  b1  6.60 – 6.90 GHz
  b0  7.00 – 7.20 GHz  OR  8.50 – 9.40 GHz (EM coupling shifts b0 when b1 absent)
"""

import os
import sys
import numpy as np
from scipy.signal import find_peaks

# ── INVENTORY ────────────────────────────────────────────────────────────────
INVENTORY = [
    {"code":"00000","dec":0,  "name":"Ballpoint Pens (Blue)",  "cat":"Writing",     "zone":"Shelf A1","status":"In Stock",    "scan":"10 min ago","desc":"Box of 50 blue ballpoint pens, 0.7 mm tip. Standard issue."},
    {"code":"00001","dec":1,  "name":"Ballpoint Pens (Black)", "cat":"Writing",     "zone":"Shelf A1","status":"In Stock",    "scan":"10 min ago","desc":"Box of 50 black ballpoint pens, 0.7 mm tip. Refillable barrel."},
    {"code":"00010","dec":2,  "name":"Gel Pens (Assorted)",    "cat":"Writing",     "zone":"Shelf A2","status":"Low Stock",   "scan":"2 hrs ago", "desc":"Pack of 12 gel ink pens, 0.5 mm fine tip, assorted colours."},
    {"code":"00011","dec":3,  "name":"Mechanical Pencils",     "cat":"Writing",     "zone":"Shelf A2","status":"In Stock",    "scan":"1 hr ago",  "desc":"Pack of 10 mechanical pencils, 0.5 mm lead, built-in eraser."},
    {"code":"00100","dec":4,  "name":"Wooden Pencils HB",      "cat":"Writing",     "zone":"Shelf A3","status":"In Stock",    "scan":"3 hrs ago", "desc":"Box of 72 pre-sharpened HB pencils, FSC-certified wood."},
    {"code":"00101","dec":5,  "name":"Highlighters (6-Pack)",  "cat":"Marking",     "zone":"Shelf A3","status":"In Stock",    "scan":"45 min ago","desc":"6 chisel-tip highlighters: yellow, green, pink, orange, blue, purple."},
    {"code":"00110","dec":6,  "name":"Whiteboard Markers",     "cat":"Marking",     "zone":"Shelf B1","status":"In Stock",    "scan":"5 hrs ago", "desc":"Pack of 8 dry-erase markers, bullet tip, low-odour ink."},
    {"code":"00111","dec":7,  "name":"Permanent Markers",      "cat":"Marking",     "zone":"Shelf B1","status":"In Stock",    "scan":"1 hr ago",  "desc":"Pack of 4 black permanent markers, fine point, quick-drying."},
    {"code":"01000","dec":8,  "name":"A4 Copier Paper",        "cat":"Paper",       "zone":"Shelf C1","status":"In Stock",    "scan":"30 min ago","desc":"Ream of 500 sheets, 80 gsm, A4 size, laser/inkjet compatible."},
    {"code":"01001","dec":9,  "name":"A3 Copier Paper",        "cat":"Paper",       "zone":"Shelf C1","status":"Low Stock",   "scan":"1 day ago", "desc":"Ream of 250 sheets, 80 gsm, A3 size, multipurpose."},
    {"code":"01010","dec":10, "name":"Sticky Notes (3×3)",     "cat":"Paper",       "zone":"Shelf C2","status":"In Stock",    "scan":"6 hrs ago", "desc":"12 pads × 100 sheets, 3×3 inch, neon assorted, repositionable."},
    {"code":"01011","dec":11, "name":"Sticky Notes (Large)",   "cat":"Paper",       "zone":"Shelf C2","status":"In Stock",    "scan":"2 days ago","desc":"4 ruled pads × 100 sheets, 4×6 inch, canary yellow."},
    {"code":"01100","dec":12, "name":"Spiral Notebooks",       "cat":"Notebooks",   "zone":"Shelf C3","status":"In Stock",    "scan":"3 hrs ago", "desc":"5 spiral-bound A5 notebooks, 200 pages each, ruled."},
    {"code":"01101","dec":13, "name":"Composition Books",      "cat":"Notebooks",   "zone":"Shelf C3","status":"In Stock",    "scan":"20 min ago","desc":"3 hardcover A4 composition books, 100 pages, graph-ruled."},
    {"code":"01110","dec":14, "name":"Legal Pads",             "cat":"Notebooks",   "zone":"Shelf C4","status":"In Stock",    "scan":"15 min ago","desc":"6 canary legal pads, 8.5×11 inch, 50 sheets, wide-ruled."},
    {"code":"01111","dec":15, "name":"Erasers (Pack)",         "cat":"Accessories", "zone":"Shelf D1","status":"In Stock",    "scan":"4 hrs ago", "desc":"Pack of 20 white vinyl erasers, smudge-free, individually sleeved."},
    {"code":"10000","dec":16, "name":"Pencil Sharpeners",      "cat":"Accessories", "zone":"Shelf D1","status":"In Stock",    "scan":"1 day ago", "desc":"12 single-hole metal sharpeners, durable blade, shavings container."},
    {"code":"10001","dec":17, "name":"Rulers 30 cm",           "cat":"Measuring",   "zone":"Shelf D2","status":"In Stock",    "scan":"1 hr ago",  "desc":"10 clear plastic rulers, 30 cm / 12 inch, shatter-resistant."},
    {"code":"10010","dec":18, "name":"Scissors",               "cat":"Cutting",     "zone":"Shelf D2","status":"In Stock",    "scan":"2 hrs ago", "desc":"6 stainless steel scissors, 8 inch, comfort-grip handles."},
    {"code":"10011","dec":19, "name":"Craft Knife Set",        "cat":"Cutting",     "zone":"Shelf D3","status":"Checked Out","scan":"35 min ago","desc":"Precision craft knife, 10 blades, safety cap."},
    {"code":"10100","dec":20, "name":"Tape Dispenser",         "cat":"Adhesives",   "zone":"Shelf E1","status":"In Stock",    "scan":"5 hrs ago", "desc":"Weighted desktop tape dispenser, non-slip base, 19 mm rolls."},
    {"code":"10101","dec":21, "name":"Clear Tape Rolls",       "cat":"Adhesives",   "zone":"Shelf E1","status":"In Stock",    "scan":"40 min ago","desc":"8 clear tape rolls, 19 mm × 33 m, invisible on paper."},
    {"code":"10110","dec":22, "name":"Glue Sticks",            "cat":"Adhesives",   "zone":"Shelf E2","status":"In Stock",    "scan":"8 hrs ago", "desc":"24 washable glue sticks, 21 g each, non-toxic, dries clear."},
    {"code":"10111","dec":23, "name":"Correction Tape",        "cat":"Accessories", "zone":"Shelf E2","status":"Low Stock",   "scan":"1 day ago", "desc":"6 correction tape rollers, 5 mm × 8 m, instant dry."},
    {"code":"11000","dec":24, "name":"Stapler (Desktop)",      "cat":"Fastening",   "zone":"Shelf F1","status":"In Stock",    "scan":"6 hrs ago", "desc":"Full-strip stapler, 25-sheet capacity, 26/6 staples."},
    {"code":"11001","dec":25, "name":"Staples (Box)",          "cat":"Fastening",   "zone":"Shelf F1","status":"In Stock",    "scan":"7 days ago","desc":"5,000 standard 26/6 galvanised steel staples."},
    {"code":"11010","dec":26, "name":"Paper Clips (Box)",      "cat":"Fastening",   "zone":"Shelf F2","status":"In Stock",    "scan":"2 hrs ago", "desc":"500 silver paper clips, 28 mm, smooth round wire."},
    {"code":"11011","dec":27, "name":"Binder Clips",           "cat":"Fastening",   "zone":"Shelf F2","status":"In Stock",    "scan":"12 hrs ago","desc":"48 binder clips, assorted sizes (19/25/32 mm), black handles."},
    {"code":"11100","dec":28, "name":"Manila Folders",         "cat":"Filing",      "zone":"Shelf G1","status":"In Stock",    "scan":"2 days ago","desc":"50 manila A4 folders, half-cut tab, 250 gsm card."},
    {"code":"11101","dec":29, "name":"Ring Binders",           "cat":"Filing",      "zone":"Shelf G1","status":"In Stock",    "scan":"4 hrs ago", "desc":"10 ring binders, A4, 2-ring D-mechanism, 25 mm spine."},
    {"code":"11110","dec":30, "name":"Sheet Protectors",       "cat":"Filing",      "zone":"Shelf G2","status":"In Stock",    "scan":"1 day ago", "desc":"100 clear A4 sheet protectors, top-loading, 50-micron."},
    {"code":"11111","dec":31, "name":"Envelopes DL (White)",   "cat":"Mailing",     "zone":"Shelf G3","status":"In Stock",    "scan":"3 days ago","desc":"500 white DL envelopes, 110×220 mm, peel-and-seal, 80 gsm."},
]

# ── BAND DEFINITIONS ─────────────────────────────────────────────────────────
# Physics-based resonance windows corresponding to each slot resonator:
#  b4: 3.40 – 3.95 GHz
#  b3: 4.40 – 5.05 GHz
#  b2: 5.55 – 6.20 GHz
#  b1: 6.55 – 6.95 GHz
#  b0: 7.00 – 7.25 GHz (primary) or 8.40 – 9.50 GHz (EM coupling shift)
BANDS = [
    {"name": "b4", "primary": (3.40, 3.95), "alt": None,          "min_prom": 3.0, "label": "3.40–3.95 GHz"},
    {"name": "b3", "primary": (4.40, 5.05), "alt": None,          "min_prom": 3.0, "label": "4.40–5.05 GHz"},
    {"name": "b2", "primary": (5.55, 6.20), "alt": None,          "min_prom": 3.0, "label": "5.55–6.20 GHz"},
    {"name": "b1", "primary": (6.55, 6.95), "alt": None,          "min_prom": 3.0, "label": "6.55–6.95 GHz"},
    {"name": "b0", "primary": (7.00, 7.25), "alt": (8.40, 9.50),  "min_prom": 2.0, "label": "7.00–7.25 / 8.40–9.50 GHz"},
]

# ── PARSER ───────────────────────────────────────────────────────────────────
def parse_cst(text):
    freqs, rcs = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                freqs.append(float(parts[0]))
                rcs.append(float(parts[1]))
            except ValueError:
                continue
    if not freqs:
        raise ValueError("No numeric data found in file.")
    idx = np.argsort(freqs)
    return np.array(freqs)[idx], np.array(rcs)[idx]

# ── DECODER ──────────────────────────────────────────────────────────────────
def decode_rfid(freqs, rcs, base_prominence=1.0):
    # Detect candidate dips using a low threshold to ensure no shallow dip is missed
    peaks, props = find_peaks(-rcs, prominence=base_prominence)

    dips = []
    for j, i in enumerate(peaks):
        dips.append({
            "f":    round(float(freqs[i]), 4),
            "rcs":  round(float(rcs[i]), 2),
            "prom": round(float(props["prominences"][j]), 2),
        })
    dips.sort(key=lambda d: d["f"])

    # Classify bits using band ranges and physics thresholds
    bits = []
    band_results = []
    for band in BANDS:
        lo, hi = band["primary"]
        min_p = band.get("min_prom", 2.5)
        matched = None

        # Check primary band
        for d in dips:
            if lo <= d["f"] <= hi and d["prom"] >= min_p:
                if matched is None or d["prom"] > matched["prom"]:
                    matched = d

        # Check secondary / coupling shifted band if needed
        if matched is None and band["alt"]:
            lo2, hi2 = band["alt"]
            for d in dips:
                if lo2 <= d["f"] <= hi2 and d["prom"] >= min_p:
                    if matched is None or d["prom"] > matched["prom"]:
                        matched = d

        bit = "1" if matched else "0"
        bits.append(bit)
        band_results.append({"band": band, "dip": matched, "bit": bit})

    code = "".join(bits)
    dec  = int(code, 2)
    return {
        "code":         code,
        "decimal":      dec,
        "dips":         dips,
        "band_results": band_results,
        "item":         INVENTORY[dec] if 0 <= dec < len(INVENTORY) else None,
        "n_points":     len(freqs),
        "freq_range":   (round(float(freqs[0]), 2), round(float(freqs[-1]), 2)),
    }

def decode_file(path, base_prominence=1.0):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    freqs, rcs = parse_cst(text)
    result = decode_rfid(freqs, rcs, base_prominence)
    result["file"] = os.path.basename(path)
    return result

# ── CLI OUTPUT ───────────────────────────────────────────────────────────────
def print_result(res):
    print("=" * 62)
    print("  CST CHIPLESS RFID DECODER")
    if "file" in res:
        print(f"  File:   {res['file']}")
    print(f"  Range:  {res['freq_range'][0]} – {res['freq_range'][1]} GHz  ({res['n_points']} points)")
    print("=" * 62)

    print(f"\n{'Bit':<5} {'Band':<27} {'State':<12} {'Dip (GHz)':<12} {'Prom (dB)'}")
    print("-" * 62)
    for br in res["band_results"]:
        d  = br["dip"]
        st = "[1] DIP " if br["bit"] == "1" else "[0] FLAT"
        f  = f"{d['f']:.3f}" if d else "—"
        p  = f"{d['prom']:.2f}" if d else "—"
        print(f"{br['band']['name']:<5} {br['band']['label']:<27} {st:<12} {f:<12} {p}")
    print("-" * 62)
    print(f"  Decoded tag:  {res['code']}  (decimal {res['decimal']})")

    it = res["item"]
    if it:
        print(f"\n  Item:     {it['name']}")
        print(f"  Category: {it['cat']}")
        print(f"  Location: {it['zone']}")
        print(f"  Status:   {it['status']}")
        print(f"  Scanned:  {it['scan']}")
        print(f"  Desc:     {it['desc']}")
    print("=" * 62)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:  python rfid_decoder.py <cst_file.txt>")
        sys.exit(0)
    result = decode_file(sys.argv[1])
    print_result(result)
