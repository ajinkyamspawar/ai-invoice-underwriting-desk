import json, random, string
from datetime import date, timedelta
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer

random.seed(42)
OUT = Path("data/invoices")
OUT.mkdir(parents=True, exist_ok=True)
CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def check_char(g14):
    total = 0
    for i, ch in enumerate(g14):
        prod = CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += prod // 36 + prod % 36
    return CHARS[(36 - total % 36) % 36]

def make_gstin():
    state = random.choice(["27", "29", "24", "33", "07"])
    pan = ("".join(random.choices(string.ascii_uppercase, k=5))
           + "".join(random.choices(string.digits, k=4))
           + random.choice(string.ascii_uppercase))
    g14 = state + pan + "1Z"
    return g14 + check_char(g14)

SELLERS = [{"name": n, "gstin": make_gstin()} for n in [
    "Shree Ganesh Fasteners", "Patil Auto Components", "Mehta Packaging Works",
    "Sai Textile Mills", "Kumar Precision Tools", "Bharat Polymers",
    "Om Sai Engineering", "Deccan Wiring Systems", "Lakshmi Industrial Supplies",
    "Rajesh Metal Works"]]

BUYERS = [{"name": n, "ticker": t, "gstin": make_gstin()} for n, t in [
    ("Reliance Industries Ltd", "RELIANCE.NS"), ("Tata Motors Ltd", "TATAMOTORS.NS"),
    ("Infosys Ltd", "INFY.NS"), ("Larsen & Toubro Ltd", "LT.NS"),
    ("Hindustan Unilever Ltd", "HINDUNILVR.NS"), ("Tata Steel Ltd", "TATASTEEL.NS"),
    ("Asian Paints Ltd", "ASIANPAINT.NS"), ("Maruti Suzuki India Ltd", "MARUTI.NS"),
    ("Adani Enterprises Ltd", "ADANIENT.NS"), ("Vodafone Idea Ltd", "IDEA.NS")]]

ITEMS = [("Steel fasteners M12", 40, 120), ("Packaging cartons", 15, 60),
         ("Auto wiring harness", 300, 900), ("Cotton fabric (metre)", 80, 250),
         ("Industrial lubricant (litre)", 150, 400), ("Plastic moulded parts", 50, 200)]

def build(n, error):
    seller, buyer = random.choice(SELLERS), random.choice(BUYERS)
    inv_date = date.today() - timedelta(days=random.randint(5, 60))
    if error == "future_date":
        inv_date = date.today() + timedelta(days=random.randint(15, 45))
    terms = random.choice([60, 90])
    items = []
    for _ in range(random.randint(2, 4)):
        d, lo, hi = random.choice(ITEMS)
        qty, rate = random.randint(10, 200), random.randint(lo, hi)
        items.append({"description": d, "qty": qty, "rate": rate, "amount": qty * rate})
    subtotal = sum(i["amount"] for i in items)
    tax = round(subtotal * 0.09, 2)
    total = round(subtotal + 2 * tax, 2)
    buyer_gstin = buyer["gstin"]
    if error == "wrong_total":
        total = round(total + random.choice([-1, 1]) * random.randint(500, 5000), 2)
    if error == "bad_gstin":
        buyer_gstin = buyer_gstin[:-1] + ("A" if buyer_gstin[-1] != "A" else "B")
    return {
        "file": f"inv_{n:02d}.pdf", "invoice_no": f"INV/2026/{n:04d}",
        "invoice_date": inv_date.isoformat(),
        "due_date": (inv_date + timedelta(days=terms)).isoformat(),
        "seller_name": seller["name"], "seller_gstin": seller["gstin"],
        "buyer_name": buyer["name"], "buyer_ticker": buyer["ticker"],
        "buyer_gstin": buyer_gstin, "items": items,
        "subtotal": subtotal, "cgst": tax, "sgst": tax, "total": total,
        "planted_error": error or "clean"}

def fmt(d):
    return date.fromisoformat(d).strftime("%d-%m-%Y")

def render(inv, path):
    s = getSampleStyleSheet()
    el = [Paragraph("TAX INVOICE", s["Title"]),
          Paragraph(f"<b>Invoice No:</b> {inv['invoice_no']} &nbsp;&nbsp; "
                    f"<b>Date:</b> {fmt(inv['invoice_date'])} &nbsp;&nbsp; "
                    f"<b>Due:</b> {fmt(inv['due_date'])}", s["Normal"]),
          Spacer(1, 10),
          Paragraph(f"<b>Seller:</b> {inv['seller_name']}<br/>GSTIN: {inv['seller_gstin']}", s["Normal"]),
          Spacer(1, 6),
          Paragraph(f"<b>Buyer:</b> {inv['buyer_name']}<br/>GSTIN: {inv['buyer_gstin']}", s["Normal"]),
          Spacer(1, 12)]
    rows = [["Description", "Qty", "Rate (Rs.)", "Amount (Rs.)"]]
    for i in inv["items"]:
        rows.append([i["description"], i["qty"], f"{i['rate']:,.2f}", f"{i['amount']:,.2f}"])
    rows += [["", "", "Subtotal", f"{inv['subtotal']:,.2f}"],
             ["", "", "CGST 9%", f"{inv['cgst']:,.2f}"],
             ["", "", "SGST 9%", f"{inv['sgst']:,.2f}"],
             ["", "", "TOTAL", f"{inv['total']:,.2f}"]]
    t = Table(rows, colWidths=[220, 50, 100, 110])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                           ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                           ("FONTNAME", (2, -1), (-1, -1), "Helvetica-Bold")]))
    el.append(t)
    SimpleDocTemplate(str(path), pagesize=A4).build(el)

plan = ["clean"] * 18 + ["wrong_total"] * 4 + ["bad_gstin"] * 3 + ["future_date"] * 2
random.shuffle(plan)
records = []
for n, err in enumerate(plan, start=1):
    inv = build(n, None if err == "clean" else err)
    render(inv, OUT / inv["file"])
    records.append(inv)

clean = [r for r in records if r["planted_error"] == "clean"]
for k, src in enumerate(random.sample(clean, 3), start=1):
    dup = dict(src)
    dup["file"], dup["planted_error"] = f"dup_{k:02d}.pdf", "duplicate"
    render(dup, OUT / dup["file"])
    records.append(dup)

Path("data/ground_truth.json").write_text(json.dumps(records, indent=2))
print(f"Generated {len(records)} invoices in {OUT}")