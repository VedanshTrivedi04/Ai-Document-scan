# 💰 Cost, Investment & Profit Analysis
## Deployment Economics for PRAGATI02 (DocSure / Pramaan)

> **Note:** Is document ke saare numbers **estimates** hain. Assumptions: ₹85 = $1, public cloud pricing jo likhte waqt maloom thi. Live pricing (Azure, Groq, OpenAI) deploy se pehle verify karein. Ye forecast nahi, planning ka andaza hai.
>
> Related docs: [REAL_WORLD_PROBLEM_AND_SOLUTION.md](REAL_WORLD_PROBLEM_AND_SOLUTION.md), [BUSINESS_MODEL_AND_TRUST.md](BUSINESS_MODEL_AND_TRUST.md)

---

## 1. Per Document / Per Bundle Cost

Assumption: 1 bundle = 3-4 documents (~4 pages, ~4,500 input tokens, ~1,200 output tokens).

| Part | Cost per bundle | Note |
| :--- | :--- | :--- |
| LLM extraction (GPT-4o-mini jaisa small model) | ₹0.12 – 0.40 | Retries ke saath ₹0.40–0.70 realistic |
| OCR, local (Tesseract / PyMuPDF) | ₹0 | Sirf server CPU |
| OCR, Azure Document Intelligence (~₹0.13/page) | ~₹0.50 | Hindi scans par zyada accurate |
| Face match, rule engine, storage, bandwidth | ₹0.05 – 0.20 | |
| **Variable cost per bundle** | **₹0.30 – 1.20** | |
| **Variable cost per document** | **₹0.10 – 0.40** | |

**Dhyan dein:** ₹0.50 sirf *marginal* (variable) cost hai. Server fixed cost hai. Volume kam ho to fixed cost bundle par baant kar **₹2–5 per bundle** ho jaata hai. Isliye "Cost = ₹0" ya "90%+ margin" sirf variable cost par sahi hai.

---

## 2. Deployment Cost

### Monthly infra (pilot, ~1 lakh bundles/month tak)

| Item | ₹ / month |
| :--- | :--- |
| App + Celery workers VM (4 vCPU / 16 GB) | 6,000 – 8,000 |
| Managed PostgreSQL + Redis | 5,000 – 8,000 |
| Storage, backup, monitoring, domain / TLS | 3,000 – 5,000 |
| LLM / OCR (usage ke hisaab se) | 5,000 – 70,000 |
| **Total** | **≈ ₹20,000 – 90,000** |

### One-time kharche

| Item | ₹ |
| :--- | :--- |
| Security audit (CERT-In empanelled auditor) | 2 – 5 lakh |
| Legal, DPDP compliance, company setup, ISO prep | 2 – 4 lakh |
| Accuracy testing aur OCR hardening | Dev time |

---

## 3. Total Investment (Year 1)

| | Lean (2–3 log) | Funded (~8 log) |
| :--- | :--- | :--- |
| Team | ₹12 – 18 lakh | ₹70 – 80 lakh |
| Infra + APIs | ₹3 – 5 lakh | ₹6 – 10 lakh |
| Audit, legal, compliance | ₹4 – 8 lakh | ₹8 – 12 lakh |
| Sales, travel, pilots | ₹3 – 5 lakh | ₹10 – 15 lakh |
| **Total** | **₹22 – 36 lakh** | **₹95 lakh – 1.2 Cr** |

Government sales cycle 12–24 mahine ka hota hai aur payment 3–9 mahine late aati hai. **Runway 18–24 mahine ki rakhni chahiye.**

---

## 4. Break-even

Contribution per bundle = price − ~₹0.70 variable cost.

| Channel | Net per bundle | Lean break-even (₹3 lakh/month burn) | Funded break-even (₹10 lakh/month burn) |
| :--- | :--- | :--- | :--- |
| B2G ₹3 | ₹2.3 | ~1.3 lakh bundles/month | ~4.3 lakh bundles/month |
| B2B fintech ₹12 | ₹11.3 | ~27,000 bundles/month | ~90,000 bundles/month |
| CSC ₹10 (₹7 humara hissa) | ~₹6.3 | ~48,000 checks/month | ~1.6 lakh checks/month |

**Important:** 50 lakh applications × ₹3 = ₹1.5 Cr **revenue** hai, profit nahi. Funded team ka kharcha ~₹1.2 Cr hai, isliye sirf B2G pay-per-bundle se lagbhag kuch nahi bachega, poori scheme jeetne par bhi.

---

## 5. Profit kahan se aayega (kam risk se zyada risk)

| # | Source | Price | Speed | Remark |
| :-- | :--- | :--- | :--- | :--- |
| 1 | **B2B** (NBFC, fintech, HR/hiring, coaching, colleges) | ₹10–15 / bundle | 1–3 mahine sales cycle | Sabse tez paisa |
| 2 | **CSC / cyber cafe channel** | ~₹6 net / check | Medium | Distribution sabse bada challenge. Break-even ke liye ~1,000 active centres jo roz 5 checks karein. CSC network entry verify nahi hui |
| 3 | **SI OEM + Licence** | ₹25 lakh – 1 Cr / dept | 12–24 mahine | Sabse bada ticket. Tender me turnover, experience, ISO 27001, STQC / CERT-In audit chahiye |
| 4 | **B2G per bundle** | ₹2–4 | Slow | Volume bada, price kam. Scale ka proof, main profit nahi |
| 5 | **Affiliate (e-affidavit) aur B2C ₹9** | Chhota | Fast | Side income. Acquisition aur payment cost khaa sakte hain |

### Illustrative Year-2/3 scenario (forecast nahi)

| Stream | Calculation | Revenue |
| :--- | :--- | :--- |
| B2B | 3 clients × 30k bundles/month × ₹10 × 12 | ₹1.08 Cr |
| CSC | 500 centres × 4 checks/day × 25 din × ₹6.5 × 12 | ₹0.39 Cr |
| Government | 1 state, 20 lakh bundles × ₹3 | ₹0.60 Cr |
| **Total revenue** | | **≈ ₹2.1 Cr** |
| Variable cost | ~37 lakh bundles × ₹0.70 | ≈ ₹0.26 Cr |
| **Contribution** | | **≈ ₹1.8 Cr** |
| Funded fixed cost | | ₹1.2 – 1.5 Cr |
| **Profit (before tax)** | | **≈ ₹30 – 60 lakh / year** |

Payback: ₹1 Cr investment par lagbhag **year 3–4**. Lean route me **1.5–2.5 saal**.

---

## 6. Business doc me jo cheezein fix karni chahiye

| Doc me likha hai | Issue |
| :--- | :--- |
| "100% pakad kar High/Critical Alert" | Overclaim. "Rules ke andar aane wale conflicts pakadta hai" likhein. Accuracy abhi measured nahi hai, sirf 35/35 consistency check hai |
| "Gross margin 90%+" | Sirf variable cost par. Support, refunds, sales commission aur fixed infra count nahi |
| ₹10 / ₹7 net revenue | **GST 18%** aur payment cost count nahi. Price GST-inclusive hai ya exclusive, clear karein |
| "NSP ~1.5 Cr applications, 5 lakh+ CSC, 40% conversion" | Figures verify nahi hue. Source dein ya "approx" likhein |
| Tesseract "air-gapped, ₹0" | Hindi scans par Tesseract kamzor hai. B2G ke liye Azure ya Indian OCR vendor lagega, cost badhegi |
| "Zero retention / auto purge" | Purge task abhi built nahi hai. Roadmap me likhein, "implemented" nahi |
| "MeghRaj par deploy" | Technically possible, par empanelment aur audit process alag hai |

---

## 7. Recommended Go-to-Market Order

1. **0–6 mahine:** 2–3 B2B pilots (NBFC, HR firm, coaching institute) aur 20–50 CSC centres. Real accuracy aur real willingness-to-pay naapo.
2. **6–12 mahine:** Pilot data se accuracy report, security audit, DPDP compliance.
3. **12–24 mahine:** Government tender ya System Integrator (SI) route.
4. Pehle saal me sirf B2G par bet na lagayein.
