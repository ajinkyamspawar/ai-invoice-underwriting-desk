import json, sys
from pathlib import Path
from typing import TypedDict
from langgraph.graph import StateGraph, END
import extractor, validator, underwriter
from buyer_risk import assess

TICKERS = {"Reliance Industries Ltd": "RELIANCE.NS", "Tata Motors Ltd": "TATAMOTORS.NS",
           "Infosys Ltd": "INFY.NS", "Larsen & Toubro Ltd": "LT.NS",
           "Hindustan Unilever Ltd": "HINDUNILVR.NS", "Tata Steel Ltd": "TATASTEEL.NS",
           "Asian Paints Ltd": "ASIANPAINT.NS", "Maruti Suzuki India Ltd": "MARUTI.NS",
           "Adani Enterprises Ltd": "ADANIENT.NS", "Vodafone Idea Ltd": "IDEA.NS"}
CACHE = Path("data/extracted.json")
CONN = None

class State(TypedDict, total=False):
    path: str
    invoice: dict
    validation: dict
    risk: dict
    result: dict
    trace: list

def stub(name, band):
    return {"buyer": name, "score": 0, "band": band, "ratios": {},
            "negative_headlines": [], "headlines": []}

def extractor_agent(s):
    name = Path(s["path"]).name
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    inv = cache.get(name) or extractor.extract_invoice(s["path"])
    return {"invoice": inv, "trace": s["trace"] + [f"Extractor: read {name}"]}

def validator_agent(s):
    val = validator.validate(s["invoice"], CONN)
    return {"validation": val,
            "trace": s["trace"] + [f"Validator: {len(val['flags'])} flag(s)"]}

def risk_agent(s):
    name = s["invoice"]["buyer_name"]
    tk = TICKERS.get(name)
    risk = assess(name, tk) if tk else stub(name, "INSUFFICIENT DATA")
    return {"risk": risk,
            "trace": s["trace"] + [f"Buyer-Risk: {risk['band']} (score {risk['score']})"]}

def underwriter_agent(s):
    risk = s.get("risk") or stub(s["invoice"]["buyer_name"], "NOT ASSESSED")
    res = underwriter.underwrite(s["invoice"], s["validation"], risk)
    return {"result": res,
            "trace": s["trace"] + [f"Underwriter: {res['decision']}"]}

def route(s):
    return "underwriter_agent" if s["validation"]["flags"] else "risk_agent"

g = StateGraph(State)
g.add_node("extractor_agent", extractor_agent)
g.add_node("validator_agent", validator_agent)
g.add_node("risk_agent", risk_agent)
g.add_node("underwriter_agent", underwriter_agent)
g.set_entry_point("extractor_agent")
g.add_edge("extractor_agent", "validator_agent")
g.add_conditional_edges("validator_agent", route,
                        {"risk_agent": "risk_agent", "underwriter_agent": "underwriter_agent"})
g.add_edge("risk_agent", "underwriter_agent")
g.add_edge("underwriter_agent", END)
app = g.compile()

def run(path, conn=None):
    global CONN
    CONN = conn or validator.new_db(":memory:")
    return app.invoke({"path": path, "trace": []})

if __name__ == "__main__":
    files = sys.argv[1:] or ["inv_02.pdf", "inv_05.pdf", "inv_07.pdf"]
    conn = validator.new_db(":memory:")
    for f in files:
        out = run(f"data/invoices/{f}", conn)
        print("=" * 50)
        print(f)
        print(" -> ".join(out["trace"]))
        print("DECISION:", out["result"]["decision"], "|", out["result"]["advance_pct"], "%")