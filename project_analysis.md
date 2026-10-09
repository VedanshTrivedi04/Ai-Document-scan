# 🔍 Agnitiaa Project — Complete Analysis

---

## PART 1: YE PROJECT KYA HAI? (Scratch se samjho)

---

### 📌 Project Ka Naam
**FDDT — Fraud Document Detection Tool**
(Pehle "DocAuth" ya "Document Authenticator Tool" kehte the)

---

### 🎯 Simple Bhasha Mein: Kya Karta Hai Ye Project?

Maan lo koi company ya government office hai. Wahan log apne documents submit karte hain — jaise invoice, payment receipt, school certificate, travel claim, etc. Ab ye documents **fake ho sakte hain ya unme tampering ho sakti hai**. Manually check karna slow aur expensive hai.

Ye tool automatically:
1. **Documents upload karo** → PDF ya image
2. **AI padhta hai unhe** (OCR se text nikalti hai)
3. **Data extract karta hai** (date, amount, issuer name, etc.)
4. **Checks run karta hai** — kya document me koi fraud hai?
5. **Risk score deta hai** — kitna suspicious hai ye document?
6. **Reviewer ko dikhata hai** — wo approve/reject kare

---

### 🏗️ Architecture (Kaise Bana Hai)

```
┌─────────────────────────────────────────────────────┐
│                   FRONTEND (React + TypeScript)      │
│  Login → Case Queue → Case Detail → Settings        │
│  Port: 5173 (Vite dev server)                       │
└───────────────────┬─────────────────────────────────┘
                    │ REST API calls
┌───────────────────▼─────────────────────────────────┐
│                   BACKEND (FastAPI / Python)         │
│  Port: 8000                                         │
│  - API Routes (FastAPI)                             │
│  - Celery Workers (background jobs)                 │
│  - Services (OCR, LLM, Forensics, etc.)             │
└──────┬───────────────────────┬──────────────────────┘
       │                       │
┌──────▼──────┐    ┌───────────▼──────────┐
│ PostgreSQL  │    │ Redis (Task Queue)   │
│ Database    │    │ Celery jobs          │
│ Port: 5432  │    │ Port: 6379           │
└─────────────┘    └──────────────────────┘
       │
┌──────▼──────────────────────────────────┐
│  Azure Services (External AI)           │
│  - Azure Document Intelligence (OCR)   │
│  - Azure OpenAI (GPT — Data Extraction)│
│  - Azure Blob Storage (File Storage)   │
└─────────────────────────────────────────┘
```

---

### 🔄 Document Processing Pipeline (Step by Step)

```
User uploads PDF
      ↓
1. VALIDATION — PDF valid hai? Size < 10MB? Password protected nahi?
      ↓
2. OCR (Azure Document Intelligence)
   → Text, tables, key-value pairs extract karo
   → Word bounding boxes save karo (highlighting ke liye)
      ↓
3. LLM EXTRACTION (Azure OpenAI / GPT)
   → Document type classify karo (invoice? receipt? certificate?)
   → Core fields extract karo: issuer, date, amount, reference number
   → Additional fields bhi (jo bhi document me ho)
   → Amounts → plain float mein normalize karo
   → Dates → ISO 8601 format mein normalize karo
      ↓
4. VALIDATION CHECKS (multiple parallel tasks via Celery)
   ├── Field Validation: date future mein? amount calculation sahi?
   ├── Issuer Verification: ye issuer known hai registry mein?
   ├── Cross-Document Check: kya multiple documents ke amounts match karte hain?
   ├── PDF Forensics:
   │   ├── ELA (Error Level Analysis) — image tampering detect
   │   ├── Copy-Move — copy-paste detect
   │   ├── Metadata Forensics — PDF creation date vs document date
   │   ├── Ghost Text — deleted/edited text detect
   │   ├── Font Consistency — alag fonts se type kiya gaya?
   │   ├── Duplicate Check — same document pehle submit hua?
   │   └── Visual Inconsistency — AI se visual check
   ├── Signature Detection — signature/stamp hai?
   └── Signature Comparison — signature match karta hai reference se?
      ↓
5. RISK SCORING ENGINE
   → Har check ka result → weighted rules engine
   → 0-100 score → Low/Medium/High tier
   → Explainable findings (kaunsa rule fired?)
      ↓
6. REVIEWER SCREEN
   → Reviewer dekhe findings, highlights on document
   → Accept/Reject/Escalate decision
   → Audit log mein record
      ↓
7. PDF REPORT EXPORT
   → Full forensic report PDF mein generate
```

---

### 👥 User Roles (Kaun Kaun Use Karta Hai)

| Role | Kya Kar Sakta Hai |
|---|---|
| **User/Submitter** | Cases submit karna, apne cases dekhna |
| **Reviewer L1** | Cases review karna, approve/reject/escalate |
| **Reviewer L2** | Escalated cases handle karna, settings change |
| **Platform Admin** | Companies manage karna, global settings |

---

### 🗄️ Database Models (Kya-Kya Store Hota Hai)

| Model | Kya Hai |
|---|---|
| `Case` | Ek submission (ek set of documents) |
| `Document` | Ek PDF file within a case |
| `DocumentCheck` | Har check ka result (ELA, OCR, etc.) |
| `CrossDocumentFinding` | Documents ke beech mismatch |
| `CaseRiskAssessment` | Final risk score |
| `AuditLog` | Har action ka record |
| `IssuerRegistry` | Known vendors/issuers ka database |
| `RiskRule` | Scoring rules (configurable) |
| `User`, `Company` | Multi-tenant user management |
| `SignatureMatch` | Signature comparison results |
| `BulkUpload` | Batch upload tracking |

---

### 🖥️ Frontend Pages (UI Screens)

| Page | Description |
|---|---|
| `LoginPage` | Login screen |
| `CaseQueuePage` | Sabhi cases ki list (review queue) |
| `NewCasePage` | Naya case submit karo |
| `CaseDetailPage` | Case ka detail, document viewer, findings, decision panel |
| `BulkUploadPage` | Batch mein cases upload karo |
| `DashboardPage` | Analytics dashboard |
| `MyCasesPage` | Submitter ke apne cases |
| `AuditHistoryPage` | Audit log |
| `SettingsRiskRulesPage` | Risk rules configure karo |
| `SettingsIssuerRegistryPage` | Known issuers manage karo |
| `PlatformCompaniesPage` | Companies manage karo (admin) |

---

## PART 2: PROBLEM STATEMENT KYA KEHTA HAI?

---

### 📋 Problem Statement Summary

**Title:** AI-Based Document Contradiction Detector for Public Systems

**Problem:**
- Citizens government ke liye multiple documents submit karte hain (ID, address proof, income certificate)
- Kisi ek document mein naam "Rahul Kumar" hai, doosre mein "R. Kumar" — ye conflict hai
- Date ya address bhi alag ho sakti hai
- **Manual check slow aur error-prone hai**

**Objective:**
- Ek AI tool banao jo **citizen ke documents ke across conflicts/contradictions dhundhta ho**
- Aur **har conflict ko explain kare**

---

### ✅ Key Features Jo Chahiye The (Problem Statement Se)

| # | Required Feature | Status |
|---|---|---|
| 1 | PDFs aur images ko OCR se padho | ✅ IMPLEMENTED |
| 2 | Key details extract karo (name, date, address, etc.) | ✅ IMPLEMENTED |
| 3 | Documents ke across match karo | ✅ IMPLEMENTED |
| 4 | Spelling aur transliteration differences allow karo (fuzzy matching) | ✅ IMPLEMENTED |
| 5 | **True conflicts detect karo** with severity and exact source location | ✅ IMPLEMENTED |
| 6 | Harmless spelling differences ko ignore karo | ✅ IMPLEMENTED |
| 7 | **Reviewer screen** — accept or dismiss findings | ✅ IMPLEMENTED |
| 8 | Indian language support (bonus) | ⚠️ PARTIAL |
| 9 | Synthetic documents only | ✅ IMPLEMENTED |

---

## PART 3: KYA IMPLEMENTED HAI vs KYA NAHI

---

### ✅ JO PEHLE SE IMPLEMENT HAI (Bahut Strong)

#### 1. OCR Pipeline — ✅ FULLY DONE
- **File:** [`ocr_service.py`](file:///c:/agnitiaa/Ai-Document-scan/backend/app/services/ocr_service.py)
- Azure Document Intelligence use hota hai
- PDFs aur images dono support karta hai
- Word-level bounding boxes save hote hain (highlighting ke liye)
- Arabic text bhi handle karta hai

#### 2. LLM-Based Field Extraction — ✅ FULLY DONE
- **File:** [`llm_service.py`](file:///c:/agnitiaa/Ai-Document-scan/backend/app/services/llm_service.py)
- Azure OpenAI (GPT) se document type classify karta hai
- Core fields extract karta hai: `issuer`, `date`, `amount`, `reference_number`
- Amounts → float normalize, Dates → ISO 8601 normalize
- Arabic numerals bhi handle karta hai
- Confidence per field — low confidence pe manual review route hota hai

#### 3. Cross-Document Contradiction Detection — ✅ DONE
- **File:** [`cross_document_service.py`](file:///c:/agnitiaa/Ai-Document-scan/backend/app/services/cross_document_service.py)
- Amount, Date, Issuer compare karta hai across all documents in a case
- **Fuzzy matching** se spelling differences ignore karta hai (rapidfuzz library)
- Severity assign karta hai: `amount` mismatch = **HIGH**, baaki = medium/low
- "Claim vs Evidence" pairs ko intelligently handle karta hai (expected differences ignore)
- **Model:** `CrossDocumentFinding` table mein store hota hai

#### 4. Reviewer Screen — ✅ FULLY DONE
- **File:** [`CaseDetailPage.tsx`](file:///c:/agnitiaa/Ai-Document-scan/frontend/src/pages/CaseDetailPage.tsx)
- Document viewer with overlay highlights
- Findings list with severity
- Approve / Reject / Escalate buttons
- Activity timeline (audit log)
- PDF export

#### 5. Field-Level Validation — ✅ VERY DETAILED
- **File:** [`field_validation_service.py`](file:///c:/agnitiaa/Ai-Document-scan/backend/app/services/field_validation_service.py)
- 15+ sub-checks: date in future, amount arithmetic, IBAN validation, etc.
- Per-field bounding box locations (highlighting ke liye)

#### 6. Risk Scoring Engine — ✅ DONE
- **File:** [`risk_scoring_service.py`](file:///c:/agnitiaa/Ai-Document-scan/backend/app/services/risk_scoring_service.py)
- Weighted rules engine (not a black-box AI model)
- Configurable rules (admin UI se tune kar sakte ho)
- 0-100 score + Low/Medium/High tier
- Explainable: kaunse rules fire hue

#### 7. PDF Forensics — ✅ VERY COMPREHENSIVE
- **Files:** [`forensics/`](file:///c:/agnitiaa/Ai-Document-scan/backend/app/services/forensics/) directory
- ELA (Error Level Analysis) — pixel tampering
- Copy-Move detection — copy-paste manipulation
- Metadata forensics — PDF creation date tampering
- Ghost text — deleted/hidden text
- Font consistency — alag fonts se type kiya
- Duplicate detection — same doc submitted before

#### 8. Issuer Verification with Fuzzy + LLM — ✅ DONE
- **File:** [`issuer_service.py`](file:///c:/agnitiaa/Ai-Document-scan/backend/app/services/issuer_service.py)
- rapidfuzz se fuzzy string matching
- Cross-script matching (Arabic naam vs English registry) → LLM fallback

#### 9. Exact Conflict Location (Bounding Boxes) — ✅ DONE
- **File:** [`field_locator_service.py`](file:///c:/agnitiaa/Ai-Document-scan/backend/app/services/field_locator_service.py)
- Har field ka exact position page pe store hota hai
- PDF viewer pe highlighted overlay dikhti hai (color-coded by type)

#### 10. Multi-Tenant Platform — ✅ ENTERPRISE-GRADE
- Companies alag-alag
- Row-Level Security (PostgreSQL)
- Audit log — har action record
- Bulk upload support

#### 11. Audit Log & PDF Report — ✅ DONE
- Har action ka immutable log
- Full forensic PDF report export

---

### ⚠️ JO PARTIAL HAI

#### Indian Language Support
- **Status:** Partial
- **Kya hai:** Arabic script support hai (UAE context ke liye)
- **Kya nahi hai:**
  - Hindi/Devanagari text OCR proper support nahi
  - Indian government documents (Aadhaar, PAN, ration card) ke specific field extractors nahi hain
  - Hindi mein likhe naam ka transliteration matching nahi

#### Document Types for India
- **Status:** Partial
- **Kya hai:** Generic document classification (invoice, certificate, etc.)
- **Kya nahi hai:**
  - Aadhaar Card specific parser
  - PAN Card specific parser
  - Voter ID specific parser
  - Ration Card specific parser
  - Income Certificate (sarkari format) parser

---

### ❌ JO IMPLEMENT NAHI HAI (Problem Statement ke hisaab se gaps)

#### 1. Indian-Citizen Specific Field Mapping
- Problem statement kehta hai: "ID, address proof, income certificate"
- Abhi: Generic fields (amount, date, issuer) compare hote hain
- **Gap:** Indian government document specific fields:
  - DOB across Aadhaar + PAN + Voter ID
  - Name variations across documents (Rahul Kumar vs R. Kumar vs RAHUL KUMAR)
  - Address across documents (city, district, state separately)
  - Father's name consistency

#### 2. Name Contradiction Detection (Citizen Context)
- Abhi: `issuer` field compare hota hai (vendor/company name)
- Problem statement mein: **citizen ka naam** different documents mein compare karna
- **Gap:** "Applicant name" field across ID documents compare karna — ye specific logic nahi hai

#### 3. Address Field Cross-Comparison
- Abhi: Address field ka specific cross-document check nahi hai
- **Gap:** Address proof (utility bill, bank statement) ka address vs ID card address match karna

#### 4. "Public Systems" Integration Context
- Problem statement: "Citizens submit documents for one application"
- Abhi: Corporate/financial fraud detection context (invoices, vendor documents)
- **Gap:** Government application workflow (ek citizen ka application bundle manage karna) nahi hai

#### 5. Demo with Synthetic Indian Government Documents
- Problem statement deliverable: "Detector working on synthetic document bundles"
- **Gap:** Sample Indian government document bundles (synthetic Aadhaar + PAN + address proof sets) nahi hain

#### 6. Simple "Conflict Found" Summary for Citizens
- Problem statement: "Explains each conflict" (citizen-friendly)
- Abhi: Technical forensics findings (ELA, copy-move, etc.) dikhta hai
- **Gap:** Simple, citizen-friendly explanation ("Aapke Aadhaar mein DOB 1990-01-01 hai, lekin PAN mein 1991-02-02 hai") nahi hai

---

## PART 4: SUMMARY TABLE

| Problem Statement Requirement | Implemented? | Notes |
|---|---|---|
| Read PDFs with OCR | ✅ Yes | Azure Doc Intelligence |
| Read images with OCR | ✅ Yes | Full support |
| Pull out key details | ✅ Yes | LLM extraction |
| Match across documents | ✅ Yes | Cross-doc service |
| Allow spelling/transliteration differences | ✅ Yes | rapidfuzz + LLM |
| Ignore harmless differences | ✅ Yes | Fuzzy threshold |
| Flag real conflicts with severity | ✅ Yes | High/Medium/Low |
| Flag with exact source location | ✅ Yes | Bounding boxes + overlay |
| Reviewer screen to accept/dismiss | ✅ Yes | CaseDetailPage |
| Indian language support | ⚠️ Partial | Arabic yes, Hindi no |
| Indian govt doc types (Aadhaar, PAN) | ❌ No | Only generic types |
| Citizen name across documents | ❌ No | Only issuer/vendor |
| Address comparison across documents | ❌ No | Not implemented |
| Synthetic Indian document bundles | ❌ No | No sample docs |
| Citizen-friendly explanations | ❌ No | Technical output only |

---

## PART 5: HACKATHON KE LIYE KYA KARNA CHAHIYE

Ye project **bahut strong foundation** hai. Hackathon mein itna karna hai:

### Priority 1 — Must Do (Problem Statement ke core requirements)
1. **Indian document types add karo** — Aadhaar, PAN, Voter ID classifiers
2. **Citizen-specific fields compare karo** — Name, DOB, Address across documents
3. **Synthetic Indian document bundles banao** — demo ke liye sample docs
4. **Simple conflict explanation** — "Name mismatch: Aadhaar mein 'Rahul Kumar', PAN mein 'R. Kumar'"

### Priority 2 — Bonus
5. **Hindi/Devanagari OCR support** — Azure Doc Intelligence already karta hai, sirf enable karo
6. **Architecture diagram** update karo (deliverable requirement hai)

### Priority 3 — Already Done
7. Reviewer screen ✅
8. Severity + location ✅
9. Fuzzy matching ✅
10. OCR + LLM extraction ✅

---

> **Bottom Line:** Project abhi ek **financial fraud detection tool** hai jo corporate invoices ke liye banaya gaya hai. Problem statement chahta hai **government document contradiction detector** jo citizen documents ke liye ho. Core AI pipeline (OCR → Extract → Compare → Score → Review) wahi hai, sirf domain-specific customization chahiye!
