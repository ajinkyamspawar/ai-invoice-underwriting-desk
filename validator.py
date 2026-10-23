import re, json, sqlite3, os
from datetime import date

CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

def gstin_ok(g):
    if not PATTERN.match(g or ""):
        return False
    total = 0
    for i, ch in enumerate(g[:14]):
        prod = CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += prod // 36 + prod % 36
    return CHARS[(36 - total % 36) % 36] == g[14]

def validate(inv, conn):
    flags = []
    def add(code, detail):
        flags.append({"code": code, "detail": detail})

    for role in ("seller", "buyer"):
        if not gstin_ok(inv[f"{role}_gstin"]):
            add("INVALID_GSTIN", f"{role} GSTIN {inv[f'{role}_gstin']} fails format/checksum")

    items_sum = sum(i["amount"] for i in inv["items"])
    if abs(items_sum - inv["subtotal"]) > 0.01:
        add("SUBTOTAL_MISMATCH", f"items sum {items_sum} vs subtotal {inv['subtotal']}")
    for i in inv["items"]:
        if abs(i["qty"] * i["rate"] - i["amount"]) > 0.01:
            add("LINE_MISMATCH", f"{i['description']}: qty x rate != amount")
    expected = inv["subtotal"] + inv["cgst"] + inv["sgst"]
    if abs(expected - inv["total"]) > 0.01:
        add("TOTAL_MISMATCH", f"expected {expected:.2f}, invoice says {inv['total']}")
    if abs(inv["cgst"] - inv["sgst"]) > 0.01:
        add("TAX_SPLIT_MISMATCH", "CGST and SGST differ")

    try:
        inv_d = date.fromisoformat(inv["invoice_date"])
        due_d = date.fromisoformat(inv["due_date"])
        if inv_d > date.today():
            add("FUTURE_DATE", f"invoice dated {inv_d}")
        if due_d < inv_d:
            add("DUE_BEFORE_INVOICE", "due date earlier than invoice date")
    except ValueError:
        add("BAD_DATE_FORMAT", "dates not in YYYY-MM-DD")

    key = f"{inv['seller_gstin']}|{inv['invoice_no']}"
    if conn.execute("SELECT 1 FROM seen WHERE k=?", (key,)).fetchone():
        add("DUPLICATE", f"{key} already submitted")
    else:
        conn.execute("INSERT INTO seen VALUES (?)", (key,))
        conn.commit()

    return {"flags": flags, "fraud_suspected": len(flags) > 0}

def new_db(path="data/validator.db"):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS seen (k TEXT PRIMARY KEY)")
    return conn

if __name__ == "__main__":
    if os.path.exists("data/test.db"):
        os.remove("data/test.db")
    conn = new_db("data/test.db")
    done = json.load(open("data/extracted.json"))
    truth = {r["file"]: r for r in json.load(open("data/ground_truth.json"))}
    MAP = {"wrong_total": "TOTAL_MISMATCH", "bad_gstin": "INVALID_GSTIN",
           "future_date": "FUTURE_DATE", "duplicate": "DUPLICATE"}
    caught = planted = false_alarms = clean = 0
    for f in sorted(done, key=lambda x: (x.startswith("dup"), x)):
        codes = {fl["code"] for fl in validate(done[f], conn)["flags"]}
        err = truth[f]["planted_error"]
        if err == "clean":
            clean += 1
            if codes:
                false_alarms += 1
                print("FALSE ALARM", f, codes)
        else:
            planted += 1
            if MAP[err] in codes:
                caught += 1
            else:
                print("MISSED", f, err, codes)
    print(f"\nPlanted errors caught: {caught}/{planted}")
    print(f"False alarms on clean invoices: {false_alarms}/{clean}")