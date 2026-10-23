import json, time
from datetime import date
from pathlib import Path
import yfinance as yf
import feedparser
from urllib.parse import quote

CACHE = Path("data/buyer_risk.json")
NEG = ["fraud", "default", "downgrade", "insolvency", "nclt", "probe", "raid",
       "penalty", "sebi", "lawsuit", "loss widens", "debt", "default", "resolution"]

def pick(df, names):
    for n in names:
        if df is not None and n in df.index:
            v = df.loc[n].dropna()
            if len(v):
                return float(v.iloc[0])
    return None

def ratios(ticker):
    t = yf.Ticker(ticker)
    fin, bs = t.financials, t.balance_sheet
    ebit = pick(fin, ["EBIT", "Operating Income"])
    interest = pick(fin, ["Interest Expense"])
    revenue = pick(fin, ["Total Revenue"])
    net = pick(fin, ["Net Income"])
    ta = pick(bs, ["Total Assets"])
    equity = pick(bs, ["Stockholders Equity", "Common Stock Equity"])
    debt = pick(bs, ["Total Debt"])
    tl = pick(bs, ["Total Liabilities Net Minority Interest"])
    ca, cl = pick(bs, ["Current Assets"]), pick(bs, ["Current Liabilities"])
    re_ = pick(bs, ["Retained Earnings"])
    wc = (ca - cl) if ca is not None and cl is not None else None
    def div(a, b):
        return a / b if a is not None and b not in (None, 0) else None
    z = None
    parts = [div(wc, ta), div(re_, ta), div(ebit, ta), div(equity, tl)]
    if None not in parts:
        z = 6.56 * parts[0] + 3.26 * parts[1] + 6.72 * parts[2] + 1.05 * parts[3]
    return {"interest_coverage": div(ebit, abs(interest) if interest else None),
            "debt_to_equity": div(debt, equity) if equity and equity > 0 else None,
            "negative_equity": bool(equity is not None and equity <= 0),
            "current_ratio": div(ca, cl),
            "net_margin": div(net, revenue),
            "altman_z": z}

def band_pts(v, cuts, pts, missing, higher_better=True):
    if v is None:
        return missing
    for c, p in zip(cuts, pts):
        if (v > c) if higher_better else (v < c):
            return p
    return pts[-1]

def score(r):
    s = {}
    s["interest_coverage"] = band_pts(r["interest_coverage"], [6, 3, 1.5], [25, 18, 10, 3], 10)
    s["debt_to_equity"] = 0 if r["negative_equity"] else band_pts(
        r["debt_to_equity"], [0.5, 1, 2], [20, 15, 8, 2], 10, higher_better=False)
    s["altman_z"] = band_pts(r["altman_z"], [2.6, 1.1], [25, 12, 3], 12)
    s["current_ratio"] = band_pts(r["current_ratio"], [1.5, 1.0], [15, 10, 4], 7)
    s["net_margin"] = band_pts(r["net_margin"], [0.08, 0.03, 0], [15, 10, 5, 0], 7)
    return s

def news(name):
    url = f"https://news.google.com/rss/search?q={quote(name + ' India')}&hl=en-IN&gl=IN&ceid=IN:en"
    items = feedparser.parse(url).entries[:8]
    heads = [e.title for e in items]
    hits = [h for h in heads if any(k in h.lower() for k in NEG)]
    return heads, hits

def assess(name, ticker, force=False):
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    if ticker in cache and not force:
        return cache[ticker]
    r = ratios(ticker)
    pts = score(r)
    heads, hits = news(name)
    penalty = min(15, 5 * len(hits))
    total = max(0, sum(pts.values()) - penalty)
    known = sum(1 for k in ("interest_coverage", "debt_to_equity", "current_ratio", "net_margin", "altman_z") if r[k] is not None) + (1 if r["negative_equity"] and r["debt_to_equity"] is        	None else 0)
    band = "INSUFFICIENT DATA" if known < 3 else "LOW RISK" if total >= 70 else "MEDIUM RISK" if total >= 50 else "HIGH RISK"
    out = {"buyer": name, "ticker": ticker, "score": total, "band": band,
           "ratios": r, "points": pts, "news_penalty": penalty,
           "negative_headlines": hits, "headlines": heads, "as_of": str(date.today())}
    cache[ticker] = out
    CACHE.write_text(json.dumps(cache, indent=2))
    return out

if __name__ == "__main__":
    truth = json.load(open("data/ground_truth.json"))
    buyers = {r["buyer_name"]: r["buyer_ticker"] for r in truth}
    print(f"{'Buyer':28}{'Score':>6}  Band        D/E    Cover  AltmanZ  NewsFlags")
    for name, tk in buyers.items():
        try:
            a = assess(name, tk)
            r = a["ratios"]
            f = lambda x: "  n/a" if x is None else f"{x:5.1f}"
            print(f"{name[:27]:28}{a['score']:>6}  {a['band']:12}{f(r['debt_to_equity'])}  "
                  f"{f(r['interest_coverage'])}  {f(r['altman_z'])}    {len(a['negative_headlines'])}")
        except Exception as e:
            print(f"{name[:27]:28} FAILED: {str(e)[:60]}")
        time.sleep(2)