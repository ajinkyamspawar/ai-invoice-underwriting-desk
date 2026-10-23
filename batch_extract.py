import json, time
from pathlib import Path
import extractor

FALLBACK = "gemini-3.5-flash-lite"
PRIMARY = extractor.MODEL
truth = {r["file"]: r for r in json.load(open("data/ground_truth.json"))}
OUT = Path("data/extracted.json")
done = json.loads(OUT.read_text()) if OUT.exists() else {}
FIELDS = ["invoice_no", "invoice_date", "due_date", "seller_name", "seller_gstin",
          "buyer_name", "buyer_gstin", "subtotal", "cgst", "sgst", "total"]

def same(a, b):
    try:
        return abs(float(a) - float(b)) < 0.01
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()

for f in truth:
    if f in done:
        continue
    for model in (PRIMARY, FALLBACK):
        extractor.MODEL = model
        try:
            done[f] = extractor.extract_invoice(f"data/invoices/{f}")
            print("Extracted", f, "using", model)
            break
        except Exception as e:
            print(f"{f} failed on {model}: {str(e)[:60]}")
    extractor.MODEL = PRIMARY
    OUT.write_text(json.dumps(done, indent=2))
    time.sleep(6)

hits = {k: 0 for k in FIELDS}
perfect = 0
for f, out in done.items():
    ok = [same(out[k], truth[f][k]) for k in FIELDS]
    perfect += all(ok)
    for k, v in zip(FIELDS, ok):
        hits[k] += v
n = len(done)
print(f"\nInvoices extracted: {n}/{len(truth)}")
print(f"Fully correct invoices: {perfect}/{n}")
for k in FIELDS:
    print(f"  {k}: {hits[k]}/{n}")