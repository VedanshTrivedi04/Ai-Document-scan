# PRAMAAN — National-Level Pitch Deck
### 6-Slide · 16:9 · Government/Hackathon Jury Format

> **Design tokens quick-reference**
> | Token | Value | Use |
> |---|---|---|
> | `navy` | `#0B2545` | All headings, slide titles |
> | `trust-blue` | `#1D4ED8` | Accent lines, icons, links |
> | `saffron` | `#F59E0B` | Harmless/ignored badge |
> | `red` | `#DC2626` | Critical conflict badge only |
> | `green` | `#16A34A` | Verified / clear badge |
> | `bg` | `#F8FAFC` / white | Slide background |
> | Font EN | Inter or Poppins | All English text |
> | Font HI | Noto Sans Devanagari | All Devanagari text |
> | Footer every slide | `Pramaan · प्रमाण — Slide N of 6` | Bottom-left, 9 pt navy |

---

---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## SLIDE 1 — TITLE + THE HOOK
### Aspect ratio: 16:9 · Background: white

---

### 🔷 ACTION TITLE  
> **"Pramaan: one wrong letter shouldn't reject a citizen's application"**  
> *(12 pt caption below: "AI-Based Document Contradiction Detector for Public Systems")*  
> Font: Inter Bold · Colour: `#0B2545` · Max 12 words ✓

---

### 📐 LAYOUT STRUCTURE

```
┌─────────────────────────────────────────────────────────────────────┐
│  ACTION TITLE (full width, top)                                      │
├───────────────────────────────────┬─────────────────────────────────┤
│  LEFT 55%                         │  RIGHT 45%                       │
│  Project Identity Block           │  Visual Hook: Document Cards     │
│                                   │                                  │
│  • PRAMAAN                        │  ┌──────────┐ ┌──────────┐      │
│    (72 pt, navy, Inter ExtraBold) │  │ Aadhaar  │ │Income    │      │
│  • प्रमाण                          │  │ Rakesh   │ │Certificate│     │
│    (40 pt, Noto Sans Devanagari)  │  │ Kumar    │ │राकेश कुमार│     │
│  • Tagline                        │  │ Sharma   │ │शर्मा     │      │
│  • Team block                     │  └──────────┘ └──────────┘      │
│  • Problem statement + ID         │      ↕ SAME PERSON ✓ (green)    │
│                                   │  ┌──────────┐                   │
│                                   │  │Address   │                   │
│                                   │  │Proof     │                   │
│                                   │  │R. K. Sarma│                  │
│                                   │  └──────────┘                   │
│                                   │  DOB: 12/05/1999 vs 12/05/1998  │
│                                   │  ⛳ REAL CONFLICT (red flag)     │
└───────────────────────────────────┴─────────────────────────────────┘
│  Footer: Pramaan · प्रमाण — Slide 1 of 6           [TEAM NAME]      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 📝 ON-SLIDE TEXT CONTENT

**Project Name Block (left column):**
```
PRAMAAN
प्रमाण
```
*72 pt headline / 40 pt Devanagari — navy #0B2545*

**Tagline** *(16 pt, trust-blue, italic)*
```
"Catch the conflicts that matter.
 Ignore the ones that don't."
```

**Problem Statement** *(11 pt, navy, below tagline)*
```
AI-Based Document Contradiction Detector for Public Systems
Problem Statement ID: [PROBLEM STATEMENT ID]
Theme: [THEME NAME]
```

**Team Block** *(10 pt, medium grey #64748B)*
```
Team:  [TEAM NAME]
College: [COLLEGE NAME]
Members: [MEMBER 1]  ·  [MEMBER 2]  ·  [MEMBER 3]
         [MEMBER 4]  ·  [MEMBER 5]
```

---

**Visual Hook (right column) — Document Cards:**

> **Design note:** Three cards arranged in a slight staggered fan (no drop shadow). Use a thin `#E2E8F0` border, rounded 6 px corners, white fill. Each card shows a minimal document header icon + issuer name + name field only.

| Card | Issuer | Name shown | Script |
|---|---|---|---|
| Card 1 | Aadhaar Card | Rakesh Kumar Sharma | Latin |
| Card 2 | Income Certificate | राकेश कुमार शर्मा | Devanagari |
| Card 3 | Address Proof | R. K. Sarma | Latin (abbreviated) |

**Below all three cards:**
- Green badge `✓ Same person — transliteration variant, ignored` (`#16A34A` bg, white text, 9 pt)

**Below that, a thin divider, then two DOB rows:**
```
Aadhaar / Address Proof  →  DOB: 12 / 05 / 1999
Income Certificate       →  DOB: 12 / 05 / 1998
```
- Red badge `⚑ CRITICAL — Date of birth mismatch · 2 of 3 documents agree` (`#DC2626` bg, white, 9 pt)

---

### 🎙️ SPEAKER NOTES (target: ~30 seconds)

> *"A citizen submits three documents. His name is written three different ways — Rakesh Kumar Sharma, the Hindi equivalent, and the abbreviated R. K. Sarma — and that is completely fine. But one certificate has the wrong birth year, and that's what gets the application rejected weeks later. The officer has no easy way to tell these two cases apart quickly. Pramaan can — in seconds, with a reason."*

---
---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## SLIDE 2 — PROBLEM AND PROPOSED SOLUTION
### Aspect ratio: 16:9 · Background: #F8FAFC (very light grey)

---

### 🔷 ACTION TITLE
> **"Officers can't separate harmless differences from real conflicts, fast"**  
> Font: Inter Bold · Colour: `#0B2545`

---

### 📐 LAYOUT STRUCTURE

```
┌─────────────────────────────────────────────────────────────────────┐
│  ACTION TITLE                                                        │
├──────────────────────────────────┬──────────────────────────────────┤
│  LEFT 50% — THE PROBLEM          │  RIGHT 50% — THREE PILLARS       │
│                                  │                                  │
│  ⬛ Pain Point 1 + icon          │  ┌────────────────────────────┐  │
│  ⬛ Pain Point 2 + icon          │  │  🔍 DETECT                 │  │
│  ⬛ Pain Point 3 + icon          │  │  ─────────────────────────  │  │
│  ⬛ Pain Point 4 + icon          │  │  [description]             │  │
│                                  │  └────────────────────────────┘  │
│  ══ IMPACT STRIP (full width) ══ │  ┌────────────────────────────┐  │
│  [STAT placeholder]              │  │  ✏️ FILL                   │  │
│                                  │  │  ─────────────────────────  │  │
│                                  │  │  [description]             │  │
│                                  │  └────────────────────────────┘  │
│                                  │  ┌────────────────────────────┐  │
│                                  │  │  🔒 SECURE                 │  │
│                                  │  │  ─────────────────────────  │  │
│                                  │  │  [description]             │  │
│                                  │  └────────────────────────────┘  │
├──────────────────────────────────┴──────────────────────────────────┤
│  Footer: Pramaan · प्रमाण — Slide 2 of 6                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 📝 ON-SLIDE TEXT CONTENT

**LEFT COLUMN — The Problem**  
*(Each point: 9–11 pt · navy · left-aligned with a 20 pt line icon in trust-blue)*

| Icon | Pain Point |
|---|---|
| 📄 *documents icon* | Documents come from different issuers, scripts and typists — variation is normal, but tools treat it as fraud. |
| ⏱ *clock icon* | Manual cross-checking is slow, inconsistent and leaves no record of the reviewer's reasoning. |
| 🔍 *search icon* | Exact-match tools flag every spelling difference — burying real conflicts in noise. |
| ❌ *rejection icon* | Citizens discover the error only after rejection — another visit, another week of delay. |

**Impact Strip** *(full-width, thin trust-blue left border, 10 pt, light grey bg)*
```
📊  [STAT: % of welfare / government service applications delayed or rejected
     due to document inconsistencies — cite source, e.g., MeitY / CSC report]
```
> ⚠️ **[PLACEHOLDER — fill with verified figure before presenting]**

---

**RIGHT COLUMN — Three Pillars**  
*(Three white cards, 6 px navy top border each, stacked vertically, 10 pt body)*

**Card 1 — DETECT** *(top border: trust-blue `#1D4ED8`)*
```
🔍  DETECT
Reads PDFs and photos (English + Hindi), finds real conflicts with
severity, exact page location and a plain explanation.
Harmless name/transliteration variants are ignored — with a reason.
```

**Card 2 — FILL** *(top border: green `#16A34A`)*
```
✏️  FILL
Builds one verified citizen profile from all uploaded documents.
Auto-fills bank and government forms, citing the exact source
field for every value populated.
```

**Card 3 — SECURE** *(top border: navy `#0B2545`)*
```
🔒  SECURE
Encrypted, role-based, tamper-evident audit trail.
Document hashes anchored on blockchain — no personal data on-chain.
Every decision is logged with the reviewer's ID and timestamp.
```

---

### 🎙️ SPEAKER NOTES (target: ~60 seconds)

> *"The problem is not OCR — readable text extraction is a solved problem. The hard part is the judgment call: is this difference harmless or is it a real conflict that should block the application? Today, officers make that call manually and inconsistently. Exact-match software calls everything a conflict and creates more noise than signal.*
>
> *Pramaan has three jobs. DETECT — it reads documents in English and Hindi, normalises names and dates, and separates harmless variants from real conflicts, showing exactly where on the page the issue is and why it matters. FILL — once the documents are verified, Pramaan auto-builds a citizen profile and fills government and bank forms — every field has a traceable source. SECURE — every upload, every review decision and every data access is logged in a tamper-evident trail with document hashes anchored on a blockchain. No personal data ever leaves the on-premise boundary."*

---
---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## SLIDE 3 — TECHNICAL APPROACH
### Aspect ratio: 16:9 · Background: white

---

### 🔷 ACTION TITLE
> **"Rules first, AI where needed: explainable, fast and offline-capable"**  
> Font: Inter Bold · Colour: `#0B2545`

---

### 📐 LAYOUT STRUCTURE

```
┌─────────────────────────────────────────────────────────────────────┐
│  ACTION TITLE                                                        │
├─────────────────────────────────────────────────────────────────────┤
│  AI PIPELINE — horizontal flow diagram (main visual, ~40% height)   │
│                                                                      │
│  [Upload]→[Preprocess]→[Classify]→[OCR]→[Extract]→[Normalize]       │
│      →[Match + Golden Record]→[Decide]→[Explain + Reviewer Screen]  │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│  ARCHITECTURE STRIP — 4-layer band (~15% height)                     │
│  [Portals] → [FastAPI Gateway] → [AI Engine] → [Data Layer]         │
├─────────────────────────────────────────────────────────────────────┤
│  TECH STACK CHIPS — single row of pill badges (~10% height)          │
├─────────────────────────────────────────────────────────────────────┤
│  THREE CALLOUT BOXES — side panel or below pipeline (~20% height)    │
├─────────────────────────────────────────────────────────────────────┤
│  Footer: Pramaan · प्रमाण — Slide 3 of 6                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 📝 ON-SLIDE TEXT CONTENT

**AI PIPELINE DIAGRAM**  
*(Horizontal row of boxes + right-arrows. Box style: white fill, `#1D4ED8` border 1.5 px, rounded 4 px, 9 pt label. Arrows: trust-blue #1D4ED8.)*

```
┌──────────┐    ┌────────────────┐    ┌──────────────┐    ┌─────────────┐
│  Upload  │ →  │  Preprocess    │ →  │   Classify   │ →  │ OCR + Word  │
│  (PDF /  │    │  malware-safe  │    │  document    │    │   Boxes     │
│  image)  │    │  intake        │    │  type        │    │             │
└──────────┘    └────────────────┘    └──────────────┘    └─────────────┘
                                                                  ↓
┌─────────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│ Grounded Field      │ →  │ Normalize        │ →  │ Match +             │
│ Extraction          │    │ (names · dates   │    │ Golden Record       │
│ (fields + page loc) │    │  address · amt)  │    │ (majority rules)    │
└─────────────────────┘    └──────────────────┘    └─────────────────────┘
                                                                  ↓
          ┌────────────────────────────────────────────────────────────┐
          │  DECIDE                                                    │
          │  Rules engine → OCR uncertainty gate → LLM (ambiguous     │
          │  cases only, never sets severity, fully audited)          │
          └────────────────────────────────────────────────────────────┘
                                                                  ↓
          ┌────────────────────────────────────────────────────────────┐
          │  EXPLAIN + REVIEWER SCREEN                                 │
          │  Finding · Severity · Exact location · Plain-language why │
          └────────────────────────────────────────────────────────────┘
```

---

**4-LAYER ARCHITECTURE STRIP**  
*(Single horizontal band, alternating light/white fills, separated by right-chevrons)*

```
┌──────────────────────┐ › ┌─────────────────────┐ › ┌──────────────────┐ › ┌──────────────────────┐
│  PORTALS             │   │  FastAPI Gateway     │   │  AI Engine       │   │  Data Layer          │
│  Citizen PWA         │   │  MFA · RBAC          │   │  Celery workers  │   │  PostgreSQL          │
│  CSC Operator        │   │  Rate limiting       │   │  OCR · NLP       │   │  MinIO (encrypted)   │
│  Officer Dashboard   │   │  Audit logging       │   │  Blockchain TX   │   │  Local LLM           │
│  Issuer / Admin      │   │                      │   │                  │   │  Blockchain (hashes) │
└──────────────────────┘   └─────────────────────┘   └──────────────────┘   └──────────────────────┘
```

---

**TECH STACK CHIPS**  
*(Pill badges: trust-blue border, white fill, 8 pt Inter Medium)*

`Next.js` · `FastAPI` · `PostgreSQL` · `Redis / Celery` · `PaddleOCR / Surya` · `RapidFuzz` · `Indic Transliteration (AI4Bharat IndicXlit)` · `Ollama (local LLM)` · `Solidity / EVM` · `Docker`

---

**THREE "WHY IT'S DIFFERENT" CALLOUTS**  
*(Small white boxes with a trust-blue left accent stripe, 9 pt body)*

> **①  Custom Indic phonetic matching**  
> Sharma = Sarma → ignored as harmless.  
> Rakesh ≠ Ramesh → flagged as a critical name conflict.

> **②  Golden Record logic**  
> "2 of 3 documents agree; the income certificate is the odd one out" — majority-rules arbitration rather than any single source.

> **③  OCR-uncertainty gate**  
> A blurry scan where "1999" could read as "1990" is routed to "verify visually" — never an automated accusation.

---

### 🎙️ SPEAKER NOTES (target: ~75 seconds)

> *"Walk the pipeline left to right. The citizen or CSC operator uploads a bundle. The intake layer strips any malicious content before our AI ever touches the file. The classifier identifies document type — Aadhaar, income certificate, address proof. PaddleOCR or Surya runs with bounding-box coordinates so every extracted value is grounded to an exact location on the page.*
>
> *Extraction pulls named fields — name, DOB, address, income figure. Normalisation converts date formats, expands abbreviations, and runs our Indic phonetic matcher across name fields. The Golden Record step asks: across all documents, what does the majority say? If two of three agree, the third is the candidate for review.*
>
> *The decision layer runs rules first — clear cases resolve without AI. If OCR confidence is low, the gate sends it to visual review. Only genuinely ambiguous text semantics go to the local LLM — and the LLM explains, never decides severity. Everything works with the LLM switched off. The reviewer screen is the final output: finding, severity, location, plain-language explanation, one-click resolution."*

---
---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## SLIDE 4 — DEMO AND RESULTS
### Aspect ratio: 16:9 · Background: #F8FAFC

---

### 🔷 ACTION TITLE
> **"In seconds, the officer sees the real conflict and why"**  
> Font: Inter Bold · Colour: `#0B2545`

---

### 📐 LAYOUT STRUCTURE

```
┌─────────────────────────────────────────────────────────────────────┐
│  ACTION TITLE                                                        │
├────────────────────────────────────┬────────────────────────────────┤
│  LEFT 60% — REVIEWER WORKSPACE     │  RIGHT 40% — RESULTS TABLE     │
│  [SCREENSHOT / MOCKUP]             │                                │
│                                    │  Metric   | Target | Measured  │
│  Document viewer:                  │  ─────────┼────────┼─────────  │
│  Income cert with RED BOX on DOB   │  Recall   | ≥ 95%  |[MEASURED] │
│                                    │  Precision| ≥ 90%  |[MEASURED] │
│  Findings panel:                   │  False+   | ≤ 5%   |[MEASURED] │
│  ⛳ CRITICAL · Date of birth       │  Loc acc. | ≥ 90%  |[MEASURED] │
│  92% confidence                    │  Speed    | ≤ 20 s |[MEASURED] │
│  "Aadhaar + Address show 12 May    │  Auto-fill| ≥ 85%  |[MEASURED] │
│   1999; Income cert shows 1998.    │                                │
│   2 of 3 documents agree."        │  ⚠️ Synthetic data only        │
│                                    │  [N] bundles, injected         │
│  [Accept] [Dismiss] [Request info] │  conflicts + harmless variants │
│                                    │                                │
│  Tab: Ignored (5) — harmless       │                                │
│  variants with reasons shown       │                                │
├────────────────────────────────────┴────────────────────────────────┤
│  DEMO FLOW STRIP:  Upload → Conflicts + Ignored → Citizen link → ✓ │
├─────────────────────────────────────────────────────────────────────┤
│  Footer: Pramaan · प्रमाण — Slide 4 of 6                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 📝 ON-SLIDE TEXT CONTENT

**LEFT — Reviewer Workspace**

> **[SCREENSHOT: reviewer workspace]**  
> *(Replace with actual product screenshot before submission. Until then, use a clean wireframe mockup in navy/white/red/green consistent with the design system.)*

**Mockup annotation labels (for wireframe version):**

- **Red bounding box** on the DOB field of the income certificate image ← label: `"OCR-grounded location"`
- **Findings panel** content:
  ```
  ⛳ CRITICAL   ·   Date of birth   ·   92% confidence
  ──────────────────────────────────────────────────────
  Aadhaar Card and Address Proof both show 12 May 1999.
  Income Certificate shows 12 May 1998.
  2 of 3 documents agree. Income certificate is the outlier.
  ──────────────────────────────────────────────────────
  [ Accept ]   [ Dismiss ]   [ Request info from citizen ]
  ```
- **Ignored tab**:
  ```
  Ignored (5)   ←  tab badge in saffron #F59E0B
  ─────────────────────────────────────────────
  • Name: "Sharma" vs "Sarma" — phonetic transliteration variant, ignored
  • Name: "Rakesh" vs "राकेश" — script variant, ignored
  • Address: "Nagar" vs "Ngr" — common abbreviation, ignored
  (+ 2 more)
  ```

---

**RIGHT — Results Table**

| Metric | Target | Measured |
|---|---|---|
| Conflict recall | ≥ 95 % | `[MEASURED F1]` |
| Conflict precision | ≥ 90 % | `[MEASURED]` |
| False alarms on harmless variants | ≤ 5 % (vs `[BASELINE %]` exact-match) | `[MEASURED]` |
| Exact location accuracy | ≥ 90 % | `[MEASURED]` |
| Processing time, 4-doc bundle, CPU | ≤ 20 s | `[MEASURED]` |
| Form fields auto-filled correctly | ≥ 85 % | `[MEASURED]` |

> ⚠️ **All metrics above are Targets until replaced with measured values.**  
> Benchmark: `[N]` synthetic bundles with injected conflicts and harmless variants. **Synthetic data only.**

---

**DEMO FLOW STRIP**  
*(4 icons in a horizontal strip, connected by right-arrows, 9 pt labels below each icon)*

```
📤 Upload bundle  →  🔍 Conflicts flagged + 5 variants ignored  →  📧 Citizen gets correction link  →  ✅ Re-check turns green
```

---

### 🎙️ SPEAKER NOTES (target: ~75 seconds)

> *"[Live demo or recorded walkthrough] — The officer opens Pramaan and uploads a four-document bundle. In under twenty seconds on a standard CPU — no GPU needed — the reviewer workspace loads.*
>
> *On the left, the document viewer shows the income certificate with a red box exactly where the problem is: the date-of-birth field. The findings panel says: critical conflict, 92% confidence, and gives the plain-language explanation — two out of three documents agree on 1999; this certificate says 1998. The officer clicks Accept or Dismiss, and that decision is logged.*
>
> *Now notice the tab that says Ignored with a badge showing 5. Click it and you see five name and address differences — all harmless, all explained. This is the key requirement made visible: the system doesn't just flag the bad ones, it actively shows the officer what it chose to ignore and why. That builds trust.*
>
> *On the right, the results table shows our targets. The Measured column will be filled by the benchmark run on synthetic document bundles. We will present the actual numbers during the Q&A or live demo."*

---
---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## SLIDE 5 — FEASIBILITY, SECURITY AND VIABILITY
### Aspect ratio: 16:9 · Background: white

---

### 🔷 ACTION TITLE
> **"Built to run on-premise today, and to earn beyond government"**  
> Font: Inter Bold · Colour: `#0B2545`

---

### 📐 LAYOUT STRUCTURE

```
┌─────────────────────────────────────────────────────────────────────┐
│  ACTION TITLE                                                        │
├───────────────────────┬───────────────────────┬─────────────────────┤
│  COL 1 — FEASIBILITY  │  COL 2 — SECURITY     │  COL 3 — VIABILITY  │
│  (icon + points)      │  (icon + points)      │  (icon + points)    │
│                       │                       │                     │
│  🖥 Runs CPU-only     │  🛡 Malware-safe       │  🏛 State depts     │
│  LLM optional         │  upload + encrypt.    │  CSC network        │
│                       │                       │  Banks / NBFCs      │
│  📦 Open-source       │  🔐 Masked IDs, MFA,  │  Insurers           │
│  No paid cloud deps   │  role-based access    │  Universities       │
│                       │                       │                     │
│  🌐 Hindi + English   │  ⛓ Blockchain hash    │  💰 Annual on-prem  │
│  Recipe for more      │  anchoring; no PII    │  licence (Govt)     │
│  Indian languages     │  on-chain             │  Per-bundle API     │
│                       │                       │  (BFSI)             │
│                       │  ⚖ DPDP Act 2023 +    │                     │
│                       │  UIDAI masking norms  │  📊 Buyer KPIs:     │
│                       │  aligned              │  auto-clear rate    │
│                       │                       │  time / file        │
│                       │                       │  cost / file        │
├───────────────────────┴───────────────────────┴─────────────────────┤
│  RISK STRIP (2 items, thin trust-blue left border)                  │
│  ⚠ Real-world accuracy → consented pilot before any claims          │
│  ⚠ Hindi OCR quality → Surya fallback + transliteration-tolerant   │
├─────────────────────────────────────────────────────────────────────┤
│  Footer: Pramaan · प्रमाण — Slide 5 of 6                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 📝 ON-SLIDE TEXT CONTENT

*(Each column: white card, 6 px navy top border, 10 pt body, line icons in trust-blue)*

**COLUMN 1 — Feasibility**

| Icon | Point |
|---|---|
| 🖥 | Runs on a CPU-only machine. LLM is optional — rules engine alone handles the majority of cases. One-command Docker deploy. |
| 📦 | 100 % open-source stack. No paid cloud dependency — runs fully on-premise. |
| 🌐 | Hindi + English now. Modular pipeline provides a clear recipe for adding more Indian languages (transliteration, OCR, normalisation). |

**COLUMN 2 — Security & Trust**

| Icon | Point |
|---|---|
| 🛡 | Malware-safe upload (content disarm). All documents encrypted at rest. ID numbers masked in logs. |
| 🔐 | MFA + role-based access control. Every action logged with reviewer identity, timestamp and outcome. |
| ⛓ | Document hashes and consent receipts anchored on blockchain. Zero personal data on-chain. |
| 🤖 | Prompt-injection safe: the AI never sets severity or the final decision — a human reviewer always does. |
| ⚖ | Aligned with DPDP Act 2023 data-minimisation principles and UIDAI Aadhaar masking norms. |

**COLUMN 3 — Viability / Business Model**

| Icon | Point |
|---|---|
| 🏛 | **Target segments:** State departments · CSC network · Banks / NBFCs (KYC) · Insurance · Universities |
| 💰 | **Pricing:** Annual on-premise licence for government; per-bundle API pricing for BFSI |
| 📊 | **Buyer metrics sold on:** Auto-clear rate · Time per file · Cost per file |

**RISK STRIP**  
*(Two rows, thin `#1D4ED8` left border, 9 pt, light amber bg `#FFFBEB`)*

```
⚠  Real-world accuracy — consented pilot required before making public performance claims.
⚠  Hindi OCR quality on degraded scans — mitigated by Surya fallback engine and
   transliteration-tolerant matching (RapidFuzz + IndicXlit).
```

---

### 🎙️ SPEAKER NOTES (target: ~60 seconds)

> *"Three practical questions every serious jury asks: can you actually deploy it, is it safe to run with citizens' documents, and will anyone pay for it?*
>
> *Feasibility: this runs on a standard office machine, CPU only. The LLM is optional — a government department that doesn't trust cloud models can switch it off and Pramaan's rules engine still resolves the majority of cases. Docker, one command, done.*
>
> *Security: documents are encrypted, IDs are masked in logs, every access is logged with the reviewer's identity, and document hashes go on a blockchain — no personal data, just hashes. We are aligned with DPDP Act 2023 and UIDAI norms. The AI never sets the final decision — a human officer always does.*
>
> *Viability: we sell to state departments and CSC networks on an annual licence, and to banks and insurers on a per-bundle API. The metric we lead with is auto-clear rate — how many files can be approved without manual review. That is money.*
>
> *We have been honest about two risks: we need a consented pilot to validate real-world accuracy, and Hindi OCR on degraded scans is our most likely failure mode — we have a fallback and a mitigation."*

---
---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## SLIDE 6 — IMPACT, ROADMAP AND REFERENCES
### Aspect ratio: 16:9 · Background: #F8FAFC

---

### 🔷 ACTION TITLE
> **"Fewer rejections, faster decisions, and a decision trail people trust"**  
> Font: Inter Bold · Colour: `#0B2545`

---

### 📐 LAYOUT STRUCTURE

```
┌─────────────────────────────────────────────────────────────────────┐
│  ACTION TITLE                                                        │
├─────────────────────────────────────────────────────────────────────┤
│  IMPACT CARDS — 4 cards in a row (~30% height)                      │
│  [Citizens]  [Officers]  [Issuing Offices]  [Government]            │
├─────────────────────────────────────────────────────────────────────┤
│  ROADMAP — horizontal timeline, 4 phases (~25% height)              │
│  Week 1–2 ──► Week 3 ──► Week 4 ──► Post-hackathon                 │
├─────────────────────────────────────────────────────────────────────┤
│  REFERENCES — small text, 2 columns (~15% height)                   │
├─────────────────────────────────────────────────────────────────────┤
│  CLOSING LINE — large centred text                                  │
│  "Pramaan — proof you can trust."                                   │
│  [TEAM CONTACT / GITHUB LINK]                                       │
├─────────────────────────────────────────────────────────────────────┤
│  Footer: Pramaan · प्रमाण — Slide 6 of 6                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 📝 ON-SLIDE TEXT CONTENT

**IMPACT CARDS**  
*(4 equal-width cards, white fill, 4 px top border coloured per card, 9 pt body, icon at top)*

**Card 1 — Citizens** *(top border: green `#16A34A`)*
```
👤  Citizens
─────────────────────────────
Errors caught before submission.
Plain-language guidance in Hindi
and English. Voice assistance
for low-literacy users.
```

**Card 2 — Officers** *(top border: trust-blue `#1D4ED8`)*
```
🧑‍💼  Officers
─────────────────────────────
Review time per bundle cut from
[MANUAL MINUTES] to [MEASURED SECONDS].
Every decision is logged.
No more ad-hoc judgment calls.
```
> ⚠️ **[PLACEHOLDER — replace with real before/after timings from pilot or benchmark]**

**Card 3 — Issuing Offices** *(top border: saffron `#F59E0B`)*
```
🏢  Issuing Offices
─────────────────────────────
See which fields they consistently
issue incorrectly — and fix the
error at its source, before it
reaches citizens.
```

**Card 4 — Government** *(top border: navy `#0B2545`)*
```
🏛  Government
─────────────────────────────
Auditable, explainable, on-premise
AI — aligned with Digital India goals.
No black-box decisions.
Full consent trail per citizen.
```

---

**ROADMAP TIMELINE**  
*(Horizontal timeline: circles on a navy line, phase labels above, brief description below)*

```
      ●─────────────────────●─────────────────────●─────────────────────●
      │                     │                     │                     │
   Weeks 1–2            Week 3               Week 4              Post-Hackathon
  ───────────         ─────────────        ─────────────       ─────────────────
  Core Engine          Product Layer         Trust & Polish        Scale & Pilot

  OCR pipeline         Reviewer UI           Blockchain           CSC cluster
  Field extraction     FILL module           anchoring            or college pilot
  Conflict detection   Auto-fill forms       DPDP alignment       BFSI API launch
  Golden Record        Role-based access     Voice guidance       Department pilot
  Phonetic matcher     Audit logging         Hindi UI             [MEASURED RESULTS]
```

---

**REFERENCES**  
*(8 pt, grey `#64748B`, two-column list. Keep visible — jury members appreciate academic rigour.)*

```
Academic / Algorithmic:
• Fellegi & Sunter (1969) — "A Theory for Record Linkage."
  Journal of the American Statistical Association.
• Verhoeff (1969) — "Error Detecting Decimal Codes."

Libraries & Tools:
• PaddleOCR (PaddlePaddle, Apache 2.0)
• Surya OCR (Vikram Nair / Datalab, GPL-3.0)
• AI4Bharat IndicXlit — Indic transliteration

Regulation & Data:
• DPDP Act 2023 — Digital Personal Data Protection Act, India
• All India Pincode Directory — data.gov.in (Open Government Data)
• UIDAI — Aadhaar data masking / tokenisation norms
```

---

**CLOSING LINE**  
*(Centred, 36 pt, Inter ExtraBold, navy `#0B2545`)*

```
"Pramaan — proof you can trust."
         प्रमाण
```

*(Below, 11 pt, trust-blue)*
```
🔗  GitHub: [LINK]   ·   📧  Contact: [TEAM EMAIL]   ·   📱 [TEAM PHONE / UPI QR optional]
```

---

### 🎙️ SPEAKER NOTES (target: ~45 seconds)

> *"Four groups benefit. Citizens stop being turned away for errors they didn't make. Officers gain a tool that shows them exactly what to look at and logs every decision. Issuing offices can see their patterns and fix errors at source. And the government gets auditable, explainable AI — fully on-premise, fully aligned with Digital India.*
>
> *Here is the roadmap — four weeks from core engine to a working pilot. The hackathon prototype covers weeks one through four. Post-hackathon we take it to a CSC cluster or college for a real-world pilot, then expand to the BFSI API.*
>
> *The references are on screen — we built on sound record-linkage theory and open-source tools.*
>
> *[Pause. Look at the jury.]*
>
> *Pramaan — proof you can trust. Thank you."*

---
---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## MASTER PLACEHOLDER CHECKLIST
*(Fill every item below before the final submission)*

| # | Placeholder | Where used | Source |
|---|---|---|---|
| 1 | `[TEAM NAME]` | Slides 1, 6 footer | Your team |
| 2 | `[MEMBER 1–5]` | Slide 1 | Your team |
| 3 | `[COLLEGE NAME]` | Slide 1 | Your institution |
| 4 | `[PROBLEM STATEMENT ID]` | Slide 1 | SIH / hackathon portal |
| 5 | `[THEME NAME]` | Slide 1 | SIH / hackathon portal |
| 6 | `[STAT: rejection rate]` | Slide 2 impact strip | MeitY / CSC annual report / NITI Aayog |
| 7 | `[N]` synthetic bundles | Slide 4 footnote | Your benchmark run |
| 8 | `[MEASURED F1]` and all Measured column values | Slide 4 table | Your evaluation script |
| 9 | `[BASELINE %]` exact-match false-alarm rate | Slide 4 table | Run exact-match tool on same bundle |
| 10 | `[MANUAL MINUTES]` | Slide 6 officer card | Time a manual review, log it |
| 11 | `[MEASURED SECONDS]` | Slide 6 officer card | Time your system on the same bundle |
| 12 | `[GITHUB LINK]` | Slide 6 footer | Your repo |
| 13 | `[TEAM EMAIL / PHONE]` | Slide 6 footer | Your team |
| 14 | `[SCREENSHOT: reviewer workspace]` | Slide 4 | Capture from running demo |

---

> **© [TEAM NAME] — Pramaan · प्रमाण · All synthetic data · Built for [HACKATHON NAME]**
