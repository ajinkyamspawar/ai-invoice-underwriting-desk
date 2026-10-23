import json, os
import extractor
from google.genai import types

def decide(inv, val, risk):
    reasons = []
    if val["flags"]:
        reasons = [f"{f['code']}: {f['detail']}" for f in val["flags"]]
        return {"decision": "REJECT", "advance_pct": 0, "reasons": reasons}
    if inv["confidence"] < 0.8:
        return {"decision": "REVIEW", "advance_pct": 0,
                "reasons": [f"Low extraction confidence ({inv['confidence']})"]}
    band, score = risk["band"], risk["score"]
    if band == "INSUFFICIENT DATA":
        return {"decision": "REVIEW", "advance_pct": 0,
                "reasons": ["Not enough financial data on buyer"]}
    if band == "HIGH RISK":
        return {"decision": "REJECT", "advance_pct": 0,
                "reasons": [f"Buyer is HIGH RISK (score {score})"]}
    if band == "MEDIUM RISK" and score < 60:
        return {"decision": "REVIEW", "advance_pct": 0,
                "reasons": [f"Borderline buyer risk (score {score})"]}
    pct = 70 if band == "MEDIUM RISK" else 85
    return {"decision": "APPROVE", "advance_pct": pct,
            "reasons": [f"Invoice clean; buyer {band} (score {score})"]}

def write_memo(inv, val, risk, dec):
    facts = {"invoice_no": inv["invoice_no"], "seller": inv["seller_name"],
             "buyer": inv["buyer_name"], "invoice_total_rs": inv["total"],
             "due_date": inv["due_date"], "validation_flags": val["flags"],
             "buyer_score": risk["score"], "buyer_band": risk["band"],
             "buyer_ratios": risk["ratios"],
             "negative_headlines": risk["negative_headlines"],
             "recent_headlines": risk["headlines"][:5], "decision": dec}
    prompt = ("You are a credit underwriter at an NBFC. Write a decision memo "
              "under 120 words in plain English with 3 short parts: Decision, "
              "Key reasons, Next step. Use ONLY the facts below. Do not change "
              "the decision. Do not invent numbers.\n\n"
              + json.dumps(facts, indent=1, default=str))
    for model in dict.fromkeys([extractor.MODEL, "gemini-3.5-flash-lite"]):
        try:
            r = extractor.client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2))
            return r.text.strip()
        except Exception as e:
            print(f"(memo failed on {model}: {str(e)[:50]})")
    return (f"Decision: {dec['decision']}. Reasons: " + "; ".join(dec["reasons"])
            + " (auto-generated; LLM unavailable)")

def underwrite(inv, val, risk):
    dec = decide(inv, val, risk)
    dec["advance_amount"] = round(inv["total"] * dec["advance_pct"] / 100, 2)
    dec["memo"] = write_memo(inv, val, risk, dec)
    return dec

if __name__ == "__main__":
    import validator
    from buyer_risk import assess
    if os.path.exists("data/uw_test.db"):
        os.remove("data/uw_test.db")
    conn = validator.new_db("data/uw_test.db")
    done = json.load(open("data/extracted.json"))
    truth = {r["file"]: r for r in json.load(open("data/ground_truth.json"))}
    picks, bands = [], set()
    for f in sorted(done):
        t = truth[f]
        if t["planted_error"] != "clean":
            continue
        b = assess(t["buyer_name"], t["buyer_ticker"])["band"]
        if b not in bands:
            bands.add(b)
            picks.append(f)
    picks.append(next(f for f in sorted(done) if truth[f]["planted_error"] == "wrong_total"))
    for f in picks:
        t = truth[f]
        risk = assess(t["buyer_name"], t["buyer_ticker"])
        val = validator.validate(done[f], conn)
        out = underwrite(done[f], val, risk)
        print("=" * 60)
        print(f, "|", t["buyer_name"], "|", t["planted_error"])
        print("DECISION:", out["decision"], "| advance:", out["advance_pct"], "% = Rs.", out["advance_amount"])
        print(out["memo"])