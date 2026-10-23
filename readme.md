\# 🧾 AI Invoice-Financing Underwriting Desk



A multi-agent AI system that reads an invoice, validates it, scores the buyer's credit risk, and recommends \*\*Approve / Review / Reject\*\* with a written memo. Built with LangGraph, Gemini and Streamlit.



\*\*🔗 Live demo:\*\* \_add link after deployment\_



\## The problem

Small suppliers wait 60–90 days to be paid by large buyers. Lenders advance cash against invoices, but checking each one by hand takes 15–30 minutes and misses fake, duplicate or miscalculated invoices. This prototype cuts that to under a minute and records the reason for every decision.



\## How it works: Mermaid flowchart LR

&#x20;   A\[Invoice PDF] --> B\[1. Extractor]

&#x20;   B --> C\[2. Validator]

&#x20;   C -- flags found --> E\[4. Underwriter]

&#x20;   C -- clean --> D\[3. Buyer-Risk]

&#x20;   D --> E

&#x20;   E -- Approve / Reject --> F\[Decision memo + audit log]

&#x20;   E -- Review --> G\[Human reviewer] --> F



| Agent | Job | Tech |

|---|---|---|

| Extractor | Reads PDF into structured fields | Gemini + Pydantic schema |

| Validator | GSTIN checksum, tax maths, dates, duplicates | Plain Python rules + SQLite |

| Buyer-Risk | 0–100 score from debt, interest cover, Altman Z, news | yfinance, Google News RSS |

| Underwriter | Policy rules decide; LLM only writes the memo | Rules + Gemini |



\*\*Design choice:\*\* the LLM never makes the decision. Fixed rules do, so outcomes are consistent and auditable. LLM calls are limited to reading documents and explaining decisions.



\## Results (on 30 test invoices)

\- Extraction: \*\*30/30\*\* invoices fully correct

\- Validator: \*\*12/12\*\* planted errors caught, \*\*0/18\*\* false alarms

\- Routing: fraud flags skip the risk step; unknown buyers go to a human



\## Run locally



pip install -r requirements.txt

echo GEMINI\_API\_KEY=your\_key > .env

streamlit run app.py





\## Honest limitations

\- Invoices are \*\*synthetic\*\* (generated for this demo). No real customer data is used.

\- Extraction was tested on clean, computer-made PDFs; scanned or messy invoices will score lower.

\- Buyer risk is a transparent \*\*scorecard\*\*, not a trained model, since no public Indian default labels exist.

\- GSTINs are checked for format and checksum only, not against the live GST portal.

\- Buyer financials come from Yahoo Finance and can be missing (shown as "insufficient data" and sent to a human).

\- Prototype only. Not for real lending decisions.



\## Tech stack

Python · LangGraph · Google Gemini · Pydantic · Streamlit · SQLite · yfinance · pandas

