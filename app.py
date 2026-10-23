import json, csv, os
from datetime import datetime
from pathlib import Path
import streamlit as st
import pandas as pd
import pipeline, validator

st.set_page_config(page_title="Invoice Underwriting Desk", page_icon="🧾", layout="wide")
st.title("🧾 AI Invoice-Financing Underwriting Desk")
st.caption("4 agents: Extractor → Validator → Buyer-Risk → Underwriter. "
           "Prototype with synthetic invoices; buyer financials are real (Yahoo Finance).")

Path("data/uploads").mkdir(parents=True, exist_ok=True)
LOG = Path("data/audit_log.csv")
COLORS = {"APPROVE": "green", "REVIEW": "orange", "REJECT": "red"}

with st.sidebar:
    st.header("Choose an invoice")
    samples = sorted(p.name for p in Path("data/invoices").glob("*.pdf"))
    pick = st.selectbox("Sample invoice", ["-"] + samples)
    up = st.file_uploader("...or upload your own PDF", type="pdf")
    go = st.button("Run underwriting", type="primary")
    if st.button("Reset duplicate memory"):
        Path("data/app.db").unlink(missing_ok=True)
        st.success("Reset done")

if go:
    if up:
        path = f"data/uploads/{up.name}"
        Path(path).write_bytes(up.getvalue())
    elif pick != "-":
        path = f"data/invoices/{pick}"
    else:
        st.warning("Pick a sample or upload a PDF first.")
        st.stop()
    with st.spinner("Agents are working..."):
        conn = validator.new_db("data/app.db")
        st.session_state["out"] = pipeline.run(path, conn)
        st.session_state["file"] = Path(path).name
        st.session_state.pop("human", None)

if "out" in st.session_state:
    out, fname = st.session_state["out"], st.session_state["file"]
    inv, val, res = out["invoice"], out["validation"], out["result"]
    risk = out.get("risk")

    c = COLORS[res["decision"]]
    st.markdown(f"## :{c}[{res['decision']}]  —  advance {res['advance_pct']}% "
                f"= ₹{res['advance_amount']:,.2f}")
    st.info(" → ".join(out["trace"]))

    a, b, d = st.columns(3)
    a.metric("Invoice total", f"₹{inv['total']:,.2f}")
    b.metric("Buyer", inv["buyer_name"])
    d.metric("Buyer risk score", f"{risk['score']}/100 ({risk['band']})" if risk else "Skipped (fraud flag)")

    st.subheader("Decision memo")
    st.write(res["memo"])

    if val["flags"]:
        st.subheader("Validation flags")
        st.dataframe(pd.DataFrame(val["flags"]), use_container_width=True, hide_index=True)

    if risk and risk.get("ratios"):
        with st.expander("Buyer risk details"):
            r = risk["ratios"]
            st.write({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()})
            st.write("Latest headlines:", risk["headlines"][:5])

    with st.expander("Extracted invoice data"):
        st.json(inv)

    if res["decision"] == "REVIEW":
        st.subheader("👤 Human review needed")
        who = st.text_input("Reviewer name")
        note = st.text_input("Reason for your decision")
        col1, col2 = st.columns(2)
        final = "APPROVE" if col1.button("✅ Approve") else "REJECT" if col2.button("❌ Reject") else None
        if final and who:
            st.session_state["human"] = final
            new = not LOG.exists()
            with LOG.open("a", newline="") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(["time", "file", "ai_decision", "human_decision", "reviewer", "note"])
                w.writerow([datetime.now().isoformat(timespec="seconds"), fname,
                            res["decision"], final, who, note])
        elif final:
            st.warning("Enter reviewer name first.")
        if "human" in st.session_state:
            st.success(f"Human decision recorded: {st.session_state['human']}")

    if LOG.exists():
        with st.expander("Audit log"):
            st.dataframe(pd.read_csv(LOG), use_container_width=True, hide_index=True)
else:
    st.write("👈 Pick a sample invoice and click **Run underwriting**.")