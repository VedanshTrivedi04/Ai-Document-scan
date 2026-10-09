# 🤖 AIML Deep Analysis — Fraud Document Detection Tool (FDDT)

> **Project:** Pramaan / Ai-Document-scan  
> **Analysis Date:** October 2026 (revised 9 Oct 2026 after measurement and end-to-end runs)  
> **Architecture Style:** No custom ML training — managed/cloud or OpenAI-compatible LLM + pre-trained local models + classical CV/NLP + transparent rules

---

## 📌 Executive Summary

Is project mein **koi bhi custom-trained ML model nahi hai** — yeh ek deliberate design decision hai
(SPECIFICATION.md Section 4: "Do NOT train, fine-tune, or self-host any custom AI/ML model").
Saari intelligence **LLM (Azure OpenAI ya koi OpenAI-compatible, jaise Groq) + OCR (Azure ya local Tesseract) + do chhote pre-trained local face models (OpenCV YuNet/SFace) + classical computer vision + rules** se aati hai.

> **Revision note.** Pehla version sirf invoice-fraud pipeline cover karta tha. Ab isme (a) identity-bundle contradiction detector, (b) photograph/face check, (c) provider matrix (kaunsa check kis provider par chalta hai), (d) **measured** ELA/copy-move sensitivity, aur (e) real samples par end-to-end run ke nateeje jude hain. Jo number naapa gaya hai wo "Measured" likha hai; jo nahi naapa wo "Unverified".

---

## 🧠 AI/ML Components — Complete Map

```
Document Upload
    │
    ├── 1. Azure Document Intelligence (OCR/Layout)
    │       ↓ OCR text + tables + key-values + bounding boxes
    ├── 2. Azure OpenAI GPT-4o/4.1 — classify_and_extract()
    │       ↓ Document type + all fields (JSON-schema output)
    ├── 3. Classical CV Forensics (LOCAL — no API cost)
    │   ├── 3a. ELA (Error Level Analysis) — Pillow + NumPy + OpenCV
    │   ├── 3b. Copy-Move Detection — OpenCV BRISK + BFMatcher
    │   ├── 3c. Duplicate Detection — imagehash pHash
    │   └── 3d. PDF Metadata Forensics — pikepdf + PyMuPDF
    ├── 4. Font Consistency Analysis — OpenCV (OCR font recognition on scans)
    ├── 5. Ghost Content Detection — PyMuPDF + Azure OCR (erased text traces)
    ├── 6. Azure OpenAI Vision — Visual Inconsistency + AI-generation check
    ├── 7. Azure OpenAI Vision — Signature/Stamp Detection
    ├── 8. Issuer Matching — rapidfuzz + Azure OpenAI (LLM fallback)
    ├── 9. Field Validation — Rule-based arithmetic checks
    ├── 10. Cross-Document Service — Pairwise field comparison (invoice: amount/date/issuer)
    ├── 11. Risk Scoring Engine — Weighted rules engine (NOT ML)
    ├── 12. Identity extraction + contradiction check — LLM reads, RULES judge (name/DOB/address/income/ID)
    └── 13. Photograph check — OpenCV YuNet (detect) + SFace (describe), local, pre-trained
```

---

## 🔍 Component 1: Azure Document Intelligence — OCR/Layout

### Kaise kaam karta hai?
- **Model:** `prebuilt-layout` (Microsoft ka managed model, hum sirf call karte hain)
- **Optional add-on:** `styleFont` feature — har word ka estimated font family + italic/handwritten flag
- **Input:** PDF ka short-lived Azure SAS URL
- **Output:**
  - Full concatenated text (sab pages ka)
  - Tables (row × column cells)
  - Key-Value pairs
  - Per-word bounding boxes (normalized 0-1 page fractions)
  - Font family per word (agar styleFont enabled hai)

### Accuracy/Limitations (code mein explicitly documented):
| Signal | Status |
|--------|--------|
| Printed Arabic (MSA) | ✅ Natively supported |
| Handwritten Arabic | ❌ **Not reliably supported** — documented limitation |
| Printed English | ✅ Excellent |
| Handwritten English/signatures | ⚠️ Limited — `italic_or_handwritten` flag set |

### Kya requirements meet ho rahe hain?
- **Requirement 3.1 (OCR extraction):** ✅ Fully met
- **Requirement 3.7 (Arabic support):** ✅ Met for printed; handwritten caveat documented

---

## 🔍 Component 2: Azure OpenAI — Document Classification + Field Extraction

### Kaise kaam karta hai?
- **Model:** Azure OpenAI GPT-4o / GPT-4.1 (vision-capable deployment)
- **Single combined call:** `classify_and_extract()` — ek hi API call mein dono kaam
- **Output format:** Strict JSON schema (Azure OpenAI structured output mode)
- **Arabic/English normalization:** LLM hi normalize karta hai:
  - Arabic-Indic numerals (٠١٢...) → Western digits
  - Dates → ISO 8601 (YYYY-MM-DD)
  - Amounts → plain float + ISO 4217 currency code

### JSON Schema output fields:
```python
DocumentAnalysis:
  document_type: str           # "invoice", "school document", etc.
  document_type_confidence: float (0-1)
  issuer: {value, confidence, uncertain}
  reference_number: {value, confidence, uncertain}
  date: {value, raw_text, confidence, uncertain}  # value = ISO 8601
  amount: {value, raw_text, currency, confidence, uncertain}
  subtotal: {value, raw_text, currency, confidence, uncertain}
  tax_amount: {value, raw_text, currency, confidence, uncertain}
  tax_rate: {value, raw_text, confidence, uncertain}
  additional_fields: [{field_name, value, confidence, uncertain}, ...]
  line_items: [{description, quantity, unit_price, discount, line_total, ...}, ...]
  amount_in_words: {text, value, confidence}
```

### Key Design Decision — Template-Free Extraction:
- **Ek bhi per-type template nahi** — ek hi prompt sab document types handle karta hai
- `additional_fields` array — unknown fields ke liye open-ended storage
- Naya document type aaya → koi extra engineering nahi chahiye

### Accuracy Notes (code comments se):
| Aspect | Performance |
|--------|-------------|
| Document type classification | Configurable label list; `document_type_confidence` field |
| Arabic text extraction | ✅ LLM natively handles Arabic/English mixed docs |
| Field confidence | Per-field `uncertain: bool` flag — low confidence = auto-route to manual review |
| Amount normalization | ✅ Handles Arabic-Indic numerals, bidi reordering artifacts |

### Kya requirements meet ho rahe hain?
- **Requirement 3.1 (Classification):** ✅
- **Requirement 3.6 (Template-free, multi-type):** ✅ — explicitly implemented
- **Requirement 3.6 (confidence flags):** ✅ per-field `uncertain` flag

---

## 🔍 Component 3a: Error Level Analysis (ELA)

### Kaise kaam karta hai?
- **Library:** Pillow + NumPy + OpenCV
- **Technique:** JPEG re-compress → diff → find anomalous regions
- **Algorithm:**
  1. Page image ko `JPEG_RECOMPRESS_QUALITY=75` se re-compress karo
  2. `sqrt(diff)` non-linear error term compute karo (internal tool ka default)
  3. Page-relative **99.7th percentile threshold** se high-error pixels find karo
  4. Connected components → bounding boxes (normalized)

### Thresholds (tuned against 12 real sample documents):
```python
JPEG_RECOMPRESS_QUALITY = 75
_ERROR_PERCENTILE_THRESHOLD = 99.7   # Only top 0.3% pixels count
_MIN_ABSOLUTE_ERROR_THRESHOLD = 60   # Flat pages ke liye floor
MIN_REGION_AREA_FRACTION = 0.002     # Noise filter
MAX_REGION_AREA_FRACTION = 0.6       # Whole-page recompression exclude
```

### ⚠️ Known Limitations (spec mein explicitly noted):
- **Specificity confirmed:** 12 real clean documents pe **zero false positives** (validated)
- **Sensitivity UNverified:** 2 synthetic tampered patches flagged nahi hue (text-edge noise too similar)
- **Weakness:** Print-and-rescan tampering ke against weak
- **Scope limitation:** `has_image_content` check — sab current samples pe yeh check skip hota hai (koi raster image nahi unme)
- Weighted LOW (25) because it's a "signal, not a verdict"

### Accuracy (documented in code):
| Metric | Value |
|--------|-------|
| False Positive Rate (clean docs) | 0/12 tested = **0%** |
| True Positive Rate (tampered docs) | **Unverified** — no tampered image sample available |

---

## 🔍 Component 3b: Copy-Move Detection

### Kaise kaam karta hai?
- **Library:** OpenCV
- **Algorithm:** BRISK keypoint detector → BFMatcher radius match → distance/angle clustering
- **Fixed parameters** (tuned against real samples):

```python
DETECTOR_TYPE = "BRISK"
BRISK_THRESHOLD = 200      # Default 30 → 200 (27,630 keypoints pe worker hang karta tha!)
RESPONSE_THRESHOLD = 90
MATCHING_THRESHOLD = 20
CLUSTER_SIZE = 30           # Min cluster size (5 se 30 pe fix hua — 5 se sab 12 docs flag hote the)
MIN_REGION_AREA_FRACTION = 0.02
MAX_FILTERED_KEYPOINTS = 4000
MAX_MATCHES_TO_CLUSTER = 4000
```

### Accuracy:
| Metric | Value |
|--------|-------|
| False Positive Rate (12 real docs) | **0/12 = 0%** (zero false positives on clean samples) |
| Sensitivity (tampered) | **Unverified** — no genuinely copy-moved sample in repo |
| Weight in scoring | 35 (high — "hard to innocently explain") |

> **Note:** 12 real samples pe specificity validate hui hai, but sensitivity pe data nahi hai. Yahi ek gap hai.

---

## 🔍 Component 3c: Duplicate Detection (Perceptual Hash)

### Kaise kaam karta hai?
- **Library:** `imagehash` (pHash, 64-bit, hash_size=8)
- **Algorithm:**
  1. Har page render karo (200 DPI)
  2. pHash compute karo
  3. Company ke all historical hashes se Hamming distance compare karo
  4. Small distance = flag
- **Cross-company:** Deliberately isolated — apni company ke documents se hi compare

### Findings:
- **Exact match (SHA-256 identical):** `identical_file: True` — same file re-upload
- **Near-duplicate (pHash Hamming distance small):** Re-submission ka signal
- **Weight:** 40 (high — near-identical resubmission is strong fraud signal)

---

## 🔍 Component 3d: PDF Metadata Forensics

### Kaise kaam karta hai?
- **Libraries:** `pikepdf` + `PyMuPDF`
- **What it checks:**
  - XMP vs Info metadata date mismatches
  - Editing software fingerprints (Photoshop, iLovePDF, etc.)
  - Incremental save markers (multiple post-creation edits)
  - JavaScript / OpenAction presence
  - Orphaned PDF objects
  - Edit history anomalies

### Findings/Weights (from seed rules):
| Finding | Weight | Severity |
|---------|--------|----------|
| Editing software (Photoshop etc.) | **30** | High |
| Multiple incremental saves | **20** | High |
| Edit after final date | **22** | High |
| Creation date mismatch | **18** | High |
| Modification date mismatch | **18** | High |
| Single incremental save | 8 | Medium |
| Orphaned objects | 8 | Medium |
| Scanned doc was edited | 15 | High |
| Editable text over scan | 10 | Medium |
| Metadata entirely stripped | 12 | Medium |
| JavaScript / executable action | 10 | Medium |
| **Metadata score cap:** | **40** | — |

> **v2 Fix:** OpenAction jo sirf view settings set karta hai ab flag nahi hota (only actual executable/outward-reaching actions flag hote hain — false positive fix)

---

## 🔍 Component 4: Font Consistency Analysis

### Kaise kaam karta hai?
- **Library:** OpenCV (OCR font recognition on scanned pages) + Azure Document Intelligence styleFont
- **Two-tier:**
  - **PDF text layer (high severity):** Font names se directly — hard signal (weight: 40)
  - **Scanned page (medium severity):** OCR font estimate — softer signal (weight: 25)
- **What it detects:**
  - Ek paragraph mein alag font ka text → "typed in after"
  - Mixed font sizes in numbers → tampered figure
  - Second embedded copy of same font → subset split

### Accuracy in regression tests:
- `sample_font20.pdf` pe font-edit finding (positive control) **consistently fires** across all runs
- 40 weight — strongest signal in the system

---

## 🔍 Component 5: Ghost Content Detection

### Kaise kaam karta hai?
- **Libraries:** PyMuPDF + Azure OCR (for reading erased text traces)
- **Use case:** Scanned document jisme text layer add kiya, phir kuch text erase kiya
  - Scan image pe faint trace remains → live text layer pe nahi hai → ghost
- **LLM integration:** Vision model se "guess_erased_content" — hint for reviewer, not evidence

### Risk weights:
| Finding | Weight | Severity |
|---------|--------|----------|
| Deleted ghost block | 25 | High |
| Replaced/shortened line | 10 | Medium |

---

## 🔍 Component 6: Azure OpenAI Vision — Visual Inconsistency + AI-Generation

### Kaise kaam karta hai?
- **Model:** Azure OpenAI (same GPT-4o/4.1 vision deployment as extraction)
- **Runs per page:** **2 independent runs** — reliability ke liye
- **Surviving findings:** Sirf woh jo:
  - Dono runs mein mile, **YA**
  - Ek run mein `high` confidence ke saath

### 5 Visual Categories checked:
1. **Font consistency** — kya sab fields same font/weight mein hain?
2. **Text alignment** — baseline consistent hai?
3. **Color/contrast consistency** — koi patch different shade mein?
4. **Resolution/sharpness consistency** — koi region sharper/blurrier?
5. **Shadow/lighting consistency** — lighting direction consistent?

### 6th question — AI-Generation Assessment:
- `likely_ai_generated: bool` + `confidence: low/medium/high`
- **Weight: 6** (experimental — lowest in entire system)
- **Reason:** "Vision models over-report it on clean synthetic/scanned documents"

### ⚠️ Important Limitations:
- Vision model judgment **probabilistic** — run-to-run vary karta hai
- AI-generation detection ka real-world accuracy **unverified on scanned business documents**
- SPECIFICATION.md explicitly: "do not oversell" — advisory signal only

### Accuracy from regression tests:
- `visual_inconsistency_review` results: **deterministic replay pe identical** across all 38 files
- False positives ke liye: signature/stamp regions ko explicitly filter kiya (v2 fix)

---

## 🔍 Component 7: Azure OpenAI Vision — Signature/Stamp Detection

### Kaise kaam karta hai?
- **Model:** Azure OpenAI vision
- **Output:**
  - `signature_expected: bool` — kya is document type pe signature expected hai?
  - `regions: [DetectedSignatureRegion]` — bounding boxes + kind (signature/stamp) + legible stamp text

### Key Limitation (explicitly documented):
> "Presence/placement confirmation for a human reviewer, NOT a reliable automated identity-match"
> Do NOT oversell accuracy — yeh identity verification NAHI hai

### Signature Comparison (compare_signatures):
- **Output:** `consistent / possibly_consistent / inconsistent / cannot_determine`
- **No numeric score** — SPECIFICATION.md explicit: "never a numeric score implying precision this technique doesn't have"
- Language: "visually consistent with reference on file" — never "verified" or "confirmed"

---

## 🔍 Component 8: Issuer Matching — rapidfuzz + LLM Fallback

### Kaise kaam karta hai?
- **Layer 1:** `rapidfuzz` fuzzy string matching
  - `token_set_ratio` scorer
  - OCR noise normalization (trademark signs, bilingual names split)
  - Arabic + Latin parts ko separately match karo
- **Layer 2 (fallback):** Azure OpenAI `judge_entity_match()`
  - Tab use hota hai jab fuzzy matching fail karta hai different scripts ke liye
  - E.g. Arabic extracted name vs English-only registry entry
  - Reasoning-first schema (model reasons pehle, phir verdict)

### Accuracy observed:
| Scenario | Behavior |
|----------|----------|
| Empty registry (testcompany) | Result: `not_checked` — "nothing to check against" |
| Same script name | rapidfuzz handles it |
| Cross-script (Arabic vs English) | LLM fallback |
| Weight when unmatched | 15 |

---

## 🔍 Component 9: Field Validation (Rule-Based — No ML)

### Sub-checks:
| Sub-check | What it does | Weight if fail |
|-----------|-------------|----------------|
| `date_in_future` | Document date > today? | 25 |
| `subtotal_line_item_consistency` | Line items sum = subtotal? | 15 |
| `total_tax_consistency` | subtotal + tax = total? | 20 |
| `line_item_arithmetic` | qty × unit_price = line_total? | 25 |
| `tax_rate_consistency` | tax = tax_rate% of taxable lines? | 15 |
| `amount_in_words_consistency` | Words = numeric total? | 25 |
| `iban_trn_validation` | IBAN mod-97 checksum + bank code + TRN format | 15 |
| `period_quantity_consistency` | Billing period × months = qty? | N/A |
| `rescan_conflict` | Phone scanner watermark present? | N/A |

### Accuracy from regression tests:
- **IBAN validation:** Correctly detected all 24-char (invalid) AE IBANs in 18 synthetic samples
- **tax_rate_consistency fix:** Handles mixed-rate invoices (v2 — passes when tax = rate on any subset of lines)
- **amount_in_words:** Classic fraud signal — figures changed but words not updated

---

## 🔍 Component 10: Cross-Document Service

### Kaise kaam karta hai?
- Ek case ke sab documents ke shared fields pairwise compare karo:
  - Amount, date, vendor/issuer
- Mismatch → `CrossDocumentFinding` row (with severity)
- Only `medium`/`high` severity mismatches scored — `low` level expected claim-vs-evidence noise hai

---

## 🔍 Component 11: Risk Scoring Engine (Transparent Rules — NOT ML)

### Design:
- **Black-box ML nahi** — deliberately weighted rules
- Config-driven: `risk_rules` table, admin runtime-editable
- Score = sum of fired rule weights, capped at 100
- Tier thresholds: `low < 30`, `medium 30-59`, `high ≥ 60` (configurable)
- **Versioned rules** — historical cases ko retroactively rescore nahi kiya jaata

### Complete Weights Table:
| Rule Category | Rule | Weight | Severity |
|---------------|------|--------|----------|
| **Forensics** | Editing software (Photoshop) | 30 | High |
| | Copy-move cluster | **35** | High |
| | Font inconsistency (PDF layer) | **40** | High |
| | Duplicate submission | **40** | High |
| | Multiple incremental saves | 20 | High |
| | Edit after final date | 22 | High |
| | Anti-forensic signal (ELA) | 30 | High |
| | ELA tamper region | 25 | Medium |
| | Font inconsistency (scan/OCR) | 25 | Medium |
| | Ghost deleted block | 25 | High |
| | Date mismatch (XMP vs Info) | 18 | High |
| | Scanned doc edited | 15 | High |
| | PDF unreadable | 20 | High |
| | History edit after final date | 22 | High |
| **Consistency** | Date in future | 25 | High |
| | Amount in words mismatch | 25 | High |
| | Line item arithmetic error | 25 | High |
| | Total/tax mismatch | 20 | High |
| | IBAN/TRN invalid | 15 | Medium |
| | Subtotal/line mismatch | 15 | Medium |
| | Tax rate mismatch | 15 | Medium |
| **Visual** | Visual font inconsistency | 12 | Medium |
| | Visual color/contrast | 12 | Medium |
| | Visual alignment | 10 | Medium |
| | Visual sharpness | 10 | Medium |
| | Visual lighting | 8 | Low |
| | AI-generated suspected | **6** | Low |
| **Verification** | Issuer not in registry | 15 | Medium |
| | No signature where expected | 10 | Medium |
| | Signature comparison inconsistent | 20 | High |
| **Duplication** | Cross-case near-duplicate | 40 | High |
| | Metadata cap | **max 40** | — |

---


## 🔍 Component 12: Identity Contradiction Detector (naya)

- **Kaam:** ek insaan ke documents (ID, voter, address proof, income certificate) ek bundle me compare karna.
- **LLM sirf padhta hai:** `extract_identity()` — naam (+Latin reading), parent/spouse, DOB, gender, address, ID number, income. **Judge rules karte hain** (`services/identity_comparison.py`): deterministic, har finding ka named reason.
- **Harmless sirf named reason se:** spelling-of-same-sound, initials, Mohd/Md, another script, honorific/word-order, extra middle name, address formatting. Similarity score akela kabhi harmless nahi banata (Rahul/Rohit Verma ≈ 82% similar, par do log).
- **Severity:** info / low / medium / high / critical. Reviewer har finding accept/dismiss karta hai.
- **Risk (naya fix):** pehle in findings ke liye koi risk rule nahi tha, to "different name" wala case bhi risk 0 / "low" tha. Ab 13 `identity.*` rules hain (different person/photo = high, DOB year / gender / ID number = medium–high, one-letter slips = medium ya kam). Dismissed conflict score se hat jaata hai.
- **Approval gate (naya):** undecided high/critical conflict ke saath identity case approve nahi hota (409).

**Measured:** live LLM + real Tesseract OCR par 10 bundles (B01–B10) ground truth se exact match hue (terminal me dekha gaya; us run ka JSON report save nahi hua), B01 aur P02 ke recorded runs me bhi match. Oracle-mode (LLM ki jagah ground-truth reader) me saare 13 bundles exact match (OCR, pipeline, comparison, API real). Caveat: rules aur ground truth ek hi author ne likhe hain, to ye consistency check hai, independent accuracy nahi.

---

## 🔍 Component 13: Photograph / Face Check (naya)

| Cheez | Detail |
|---|---|
| Models | YuNet `face_detection_yunet_2023mar.onnx` + SFace `face_recognition_sface_2021dec.onnx` (OpenCV Zoo, Apache-2.0, pre-trained, SHA-256 pinned download: `python -m app.services.face_models`) |
| Chalta kahan | Local (OpenCV), koi cloud call nahi; provider-independent (Groq par bhi) |
| Compare | Har document ke faces, har pair par best-matching face pair (ghost photo / family doc se false conflict nahi) |
| Verdict | ≥0.45 match (info) · 0.25–0.45 "please look" (medium) · <0.25 different person (critical) |
| Privacy | Face description biometric template hai: API response se hata diya jaata hai; sirf face ki jagah browser ko milti hai |

**Measured (card-quality photos):** Olivetti 400 photos (40 log × 10) ko card par laga kar, JPEG q70: same-person 1,800 pairs, different 78,000. OpenCV ka default 0.363 par different-person ka **4.1%** galat accept hota tha; 0.45 par **0.55%** (same-person **99.4%** pass); 0.25 se neeche different ka **75.5%**, same ka **0%**. AUC 0.9998. Real portraits ko kharab photocopy tak degrade karne par same-person 0.77 → 0.39 (never "different"), different −0.02 → 0.30.
**End-to-end (real scans, real OCR, real face):** P01 (3 cards same person) → 3 match; P02 (voter card par doosre ka photo) → critical `photo_different_person`; P03 (poor photocopy) → match; P04 (card without photo) → compare nahi hua.
**Unverified:** age gap wale photo pairs, skin-tone/age/gender subgroup accuracy, real identity cards. Olivetti same-session photos hain.

---

## 🧭 Provider Matrix — kaunsa check kis setup par chalta hai

| Check | Azure (OCR+OpenAI) | Local OCR + OpenAI-compatible text LLM (Groq, current `.env`) |
|---|---|---|
| OCR | Azure Document Intelligence | PDF text layer + Tesseract (eng+hin) |
| Invoice extraction / issuer LLM fallback | ✅ | ✅ (quota-bound) |
| Identity extraction | ✅ | ✅ (quota-bound) |
| Visual inconsistency, AI-generation, signature detection/comparison | ✅ (vision model) | ❌ "provider reads text only" — check `failed` with a clear message, case phir bhi score hota hai |
| Metadata, ELA, copy-move, duplicate, font, ghost | ✅ local | ✅ local |
| Face check | ✅ local | ✅ local |

**Groq free tier ki real limit (is session me dekhi):** 8,000 tokens/min aur **200,000 tokens/day** (gpt-oss-120b). Ek document ~2.5–4k tokens leta hai, yani roz ~50–70 documents. Is session ke live e2e runs ne din ka quota khatam kar diya (HTTP 429 "tokens per day"). Production ke liye paid tier ya Azure chahiye.

---

## 📐 Measured: ELA aur Copy-Move ki sensitivity (pehle "Unverified" tha)

`python -m scripts.forensics_sensitivity` — identity-bundle card pages ko scan jaisa banaya (sensor noise, uneven light, JPEG), ek raster image per PDF page, phir 5 tarah:

| Kind | n | ELA flags | Copy-move flags |
|---|---|---|---|
| clean (control) | 24 | 1 | 0 |
| resaved whole page (control) | 24 | 0 | 0 |
| copy-move (likhe hue block ka copy) | 24 | 0 | **19 (79%)** |
| splice (doosre scan ka patch) | 24 | **0** | 0 |
| retype (value mita kar naya type) | 24 | **0** | 0 |

- **Copy-move:** control par 0/48 false alarm; copy-paste ka 79% pakda. Miss = kam-detail region.
- **ELA:** controls par 1/48 false alarm, aur splice/retype par **0/48 sensitivity**. Jab edited page ek baar poora re-save hota hai to recompression signal mit jaata hai aur text-edges baaki bachte hain. Block-level z-score (try kiya) bhi edited blocks ko alag nahi kar paya. Isliye ELA ko is configuration me **kamzor/low-value** maana jaye; weight kam rakhna sahi hai, aur ye signal akele par bharosa na ho. (Test `tests/test_forensics_sensitivity.py` isko pin karta hai.)
- Fraud ko asli me pakadne wale signals: metadata, font, ghost content, arithmetic, duplicate, aur copy-move.

---

## 🧪 End-to-End run on real samples (`tests/e2e`, `RUN_E2E=1`)

Real: upload endpoint + validation, local storage, OCR (PDF text layer / Tesseract), face detection, har forensic check, contradiction check, risk scoring, reviewer endpoints, bulk upload, sign-in, settings, report PDF. Replaced: DB = in-memory SQLite, Celery = in-process queue. `E2E_LLM=oracle` me sirf LLM ki jagah ground-truth reader (Groq quota khatam hone par); report me mode likha rehta hai.

**Oracle mode: 44 / 44 pass (~97 s).** Highlights:

| Area | Result |
|---|---|
| 13 identity bundles (PDF/JPG/PNG/TIFF, Hindi) | exact ground-truth findings |
| 4 photo bundles | P01 match ×3, P02 critical, P03 match, P04 not compared |
| Upload validation (7 real bad/good files) | valid 201; empty 400; truncated 422; locked 422; notes.pdf 415; photo-renamed 415; photo.jpg 415 |
| 13 invoice cases (26 real PDFs) | har case ke saare forensic checks chale; tampered Sample12/13/16/17 → high (100); clean 6/9/10/11/14/15 → low |
| Sample18 (font mismatch) | risk 0 → **40 (medium)** after the font-check fix below |
| Duplicate detection | same invoice dobara submit → flagged |
| Reviewer flow | approve with open conflict → 409; decide → profile; reject OK; audit events present |
| Bulk upload (2 bundles) | both cases created, B07 DOB conflict found |
| Sign-in / settings | login OK, wrong password 401, 63 risk rules, submitter 403 on settings |
| Forms / languages / report | form pre-fill, 13 languages, case-report PDF generated |
| Vision checks (visual review, signature) | clean "text-only provider" failure; case still scored |

**Live LLM (Groq):** B01 (3 docs) aur P02 (3 docs) recorded runs me real extraction + comparison sahi; 10/10 bundles B01–B10 pass (terminal par dekha). Invoice extraction + issuer registry match **live** aaj verify nahi ho paya (quota). Registry-match step tabhi chalta hai jab model ne issuer padha ho; oracle mode me sirf duplicate step chala.

---

## 🐞 Is revision me mile aur fix kiye gaye gaps

| # | Gap | Fix | Test |
|---|---|---|---|
| 1 | Font-consistency (sabse strong, weight 40) LLM extraction ke *baad* chalta tha: model fail/rate-limit hone par poora check silently skip. E2E me Sample18 risk 0 aaya | OCR ke turant baad, LLM se pehle chalta aur commit hota hai | `test_font_check_survives_a_model_failure` |
| 2 | Identity contradictions ka risk score 0 (critical name conflict bhi "low") | 13 `identity.*` rules + migration `d9e1f3a5b7c2` (existing companies ke liye), dismissed conflict score se bahar, review ke baad rescoring | `tests/test_identity_risk.py` (10) |
| 3 | Identity case serious unresolved conflict ke saath approve ho jaata tha | 409 gate (high/critical, undecided) | 7 tests in `test_case_actions.py` |
| 4 | Photographs compare nahi hote the | Component 13 | `tests/test_face_service.py` (22) |
| 5 | ELA/copy-move sensitivity unverified | Benchmark + measured numbers + pinned tests | `tests/test_forensics_sensitivity.py` |
| 6 | Migrations/RLS kisi real Postgres par verify nahi the | Throwaway Postgres 16 par poori chain zero se, mera migration downgrade→upgrade, aur RLS ke 17 tests pass | — |

---

## 📊 Regression Test Results — Model Accuracy Evidence

### Test Corpus:
- **38 unique documents** (by SHA-256)
- **575 total stored documents** across multiple companies
- **Determinism verified:** Second baseline run differed in **0/38 files**

### Positive Controls (signals that MUST fire):
| Signal | Before | After | Status |
|--------|--------|-------|--------|
| JavaScript actions (Sample16/17) | ✅ fired | ✅ fired | Kept |
| Font edits (text layer + OCR) | ✅ fired | ✅ fired | Kept |
| ELA regions | ✅ fired | ✅ fired | Kept |
| Copy-move clusters | ✅ fired | ✅ fired | Kept |
| Arithmetic mismatches | ✅ fired | ✅ fired | Kept |
| Duplicates | ✅ fired | ✅ fired | Kept |
| Editing software metadata | ✅ fired | ✅ fired | Kept |
| Amount in words mismatch | ✅ fired | ✅ fired | Kept |
| **Total kept:** | | | **80/82 = 97.6%** |

The 2 removed were **intentional false positive fixes** (view-setting OpenAction).

### Score changes on key documents:
| Document | Before | After | Reason |
|----------|--------|-------|--------|
| case2.pdf | 90 | 40 | False positives fixed |
| Sample12 (tampered) | 100 | 100 | Stable ✅ |
| Sample13 (ELA+copy-move) | 100 | 100 | Stable ✅ |
| Sample17 (all flags) | 100 | 100 | Stable ✅ |
| Test_Tampered_Invoice (En) | 87 | 87 | Stable ✅ |
| Test_Tampered_Invoice (Ar) | 87 | 87 | Stable ✅ |

---

## ✅ Requirements vs Implementation Gap Analysis

| Requirement | Status | Notes |
|-------------|--------|-------|
| OCR extraction (any doc type) | ✅ Met | Azure Layout model |
| Arabic support (printed) | ✅ Met | |
| Arabic support (handwritten) | ⚠️ Known gap | Documented limitation — not fixable without custom model |
| Template-free extraction | ✅ Met | Single LLM call, additional_fields array |
| Confidence flags per field | ✅ Met | `uncertain: bool` per field |
| Issuer matching | ✅ Met | rapidfuzz + LLM fallback |
| Fuzzy matching cross-script | ✅ Met | LLM fallback |
| Signature detection (presence) | ✅ Met | Vision model |
| Signature identity match | ❌ NOT built | SPECIFICATION says not to oversell — advisory only |
| Identity contradiction detection | ✅ Met | Component 12; ground-truth exact on 13 bundles |
| Photograph / face comparison across documents | ✅ Built | Component 13; thresholds measured on card-quality photos |
| Metadata forensics | ✅ Met | pikepdf + PyMuPDF |
| ELA tamper detection | ⚠️ Measured weak | 0/48 on re-saved edited scans, 1/48 false alarm; low weight is right |
| Copy-move detection | ✅ Measured | 19/24 copy-paste caught, 0/48 false alarms |
| Duplicate detection | ✅ Met | pHash working well |
| AI-generation detection | ⚠️ Experimental | Azure AI Content Safety nahi use kar sake (no such feature); vision LLM fallback — unverified accuracy |
| Risk scoring (transparent) | ✅ Met | Rules engine, not ML |
| Explainability (reason templates) | ✅ Met | Every rule has human-readable reason |
| Rule versioning (no retroactive) | ✅ Met | Immutable snapshots |
| Cross-document consistency | ✅ Met | Pairwise field comparison |
| Field arithmetic validation | ✅ Met | All sub-checks implemented |
| IBAN/TRN validation | ✅ Met | mod-97 checksum, bank code matching |
| Font consistency | ✅ Met | PDF layer + OCR on scans |
| Ghost content detection | ✅ Met | Erased text traces |

---

## 🚨 Key Gaps / Honest Limitations (revised)

1. **Live LLM extraction accuracy kam naapi gayi.** Groq quota (200k tokens/day) khatam hone se aaj invoice extraction aur issuer-registry match live nahi chal paye. Identity extraction ke live nateeje sirf B01–B10 aur P02 tak (aur wo bhi ek run).
2. **Rules aur ground truth ek hi author ke** hain: 13/13 exact match consistency check hai, independent accuracy nahi.
3. **Face check:** age-gap, demographic subgroups aur real ID cards par unmeasured; thresholds Olivetti (same-session, grey, low-res) par chune gaye. Detector ko na dikhne wala face "photo missing" nahi, "compare nahi hua" hota hai.
4. **ELA kamzor hai** re-saved scans par (0/48); isko akela signal na maanein.
5. **Vision-dependent checks** (visual inconsistency, AI-generation, signature detection/comparison) text-only provider par available nahi; AI-generation accuracy kabhi verify nahi hui; signature comparison advisory hai (design).
6. **Identity PDF report abhi identity-aware nahi hai (known, skip kiya):** critical conflict wale case ka exported report "LOW RISK / no risk rule fired", "no material mismatch on issuer, date or amount" aur invoice-jaise "Missing required field: Issuer/Date/Amount" dikhata hai. UI aur API sahi hain; sirf PDF export misleading hai.
7. **Issuer registry** khaali ho to `not_checked`; production me client ka real data chahiye.
8. **Handwritten Arabic** supported nahi (Azure ki limit). Frontend backend tests se cover nahi hai.
9. Duplicate detection real samples me alag cases ko bhi flag karta hai (Sample7/8/16/17) kyunki samples ek template share karte hain.

## 💡 Recommendations

1. Quota milte hi `E2E_LLM_CACHE=DIR RUN_E2E=1 pytest tests/e2e` live mode me chalayein (cache se agli runs free), aur invoice extraction + registry match live verify karein. Production ke liye paid LLM tier / Azure.
2. **Identity PDF report** ko identity-aware banayein: findings table + reviewer decisions, invoice sections hataayein.
3. Face thresholds apne asli documents par re-measure karein (age-gap pairs, subgroups); storing face descriptions ki legality/retention decide karein.
4. Independent evaluation set (rule-writer se alag) banayein.
5. ELA ka weight na badhayein; double-JPEG / block-grid analysis ek alag experiment hai.
6. Indian ID-specific validation (Aadhaar checksum, PAN format, pincode↔state) roadmap par.
7. Issuer registry populate karein; vision-capable model deploy karein agar signature/visual checks chahiye.
