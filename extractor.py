import os, sys, json, time
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def pick_model():
    name = os.getenv("GEMINI_MODEL")
    if name:
        return name
    bad = ("preview", "exp", "lite", "image", "tts", "live", "thinking")
    for m in client.models.list():
        n = m.name.replace("models/", "")
        if "flash" in n and not any(b in n for b in bad):
            return n
    raise RuntimeError("No flash model found. Set GEMINI_MODEL in .env")

MODEL = pick_model()

class Item(BaseModel):
    description: str
    qty: float
    rate: float
    amount: float

class Invoice(BaseModel):
    invoice_no: str
    invoice_date: str
    due_date: str
    seller_name: str
    seller_gstin: str
    buyer_name: str
    buyer_gstin: str
    items: list[Item]
    subtotal: float
    cgst: float
    sgst: float
    total: float
    confidence: float

PROMPT = """Extract the invoice fields exactly as printed. Do not fix or
correct any value, even if it looks wrong. Dates must be YYYY-MM-DD.
confidence is 0 to 1: how sure you are about the whole extraction."""

def extract_invoice(path):
    data = Path(path).read_bytes()
    part = types.Part.from_bytes(data=data, mime_type="application/pdf")
    for attempt in range(4):
        try:
            r = client.models.generate_content(
                model=MODEL,
                contents=[part, PROMPT],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Invoice,
                    temperature=0))
            return json.loads(r.text)
        except Exception as e:
            if attempt == 3:
                raise
            print(f"Retry {attempt + 1} after error: {str(e)[:80]}")
            time.sleep(15)

if __name__ == "__main__":
    fname = sys.argv[1] if len(sys.argv) > 1 else "inv_01.pdf"
    print("Model:", MODEL)
    out = extract_invoice(f"data/invoices/{fname}")
    truth = next(r for r in json.load(open("data/ground_truth.json"))
                 if r["file"] == fname)
    print(json.dumps(out, indent=2))
    print("\n--- Check against answer key ---")
    for k in ["invoice_no", "invoice_date", "due_date", "seller_name", "seller_gstin",
              "buyer_name", "buyer_gstin", "subtotal", "cgst", "sgst", "total"]:
        ok = str(out[k]) == str(truth[k])
        print(("OK       " if ok else "MISMATCH ") + k, "" if ok else f"-> got {out[k]}, want {truth[k]}")