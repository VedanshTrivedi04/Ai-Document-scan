# PPT Diagrams — AI Document Contradiction Detector (PRAGATI02)

How to use: paste any block into https://mermaid.live , then Actions -> PNG/SVG -> insert in PPT.
(Or in PowerPoint: Insert -> Pictures.) All data shown is synthetic.

---

## 1. System Architecture (High Level)

```mermaid
flowchart LR
    subgraph Users
        C[Citizen / Family Head]
        R[Reviewer L1 / L2]
        A[Platform Admin]
    end
    subgraph Frontend["Frontend (React + TypeScript + Vite)"]
        UI[Upload, Case Detail,<br/>Family, Forms, Dashboard]
    end
    subgraph Backend["Backend (FastAPI)"]
        API[REST API<br/>JWT + RBAC]
        ENG[Comparison Engine<br/>rules only]
        MSG[Message Builder<br/>13 languages]
    end
    subgraph Workers["Celery Workers"]
        EXQ[extraction_queue<br/>OCR + LLM extract]
        FOQ[forensics_queue<br/>cross-doc checks + forensics]
    end
    subgraph Data["Data Layer"]
        PG[(PostgreSQL<br/>Row-Level Security)]
        RD[(Redis<br/>queue + cache)]
        BL[(Blob Storage<br/>immutable originals)]
    end
    subgraph Cloud["External AI Services"]
        OCR[OCR<br/>Document Intelligence]
        LLM[LLM extraction<br/>Azure OpenAI / Groq]
        GT[Google Translate<br/>templates only]
    end
    C --> UI
    R --> UI
    A --> UI
    UI --> API
    API --> PG
    API --> BL
    API --> RD
    RD --> EXQ
    RD --> FOQ
    EXQ --> OCR
    EXQ --> LLM
    EXQ --> PG
    FOQ --> ENG
    ENG --> PG
    API --> MSG
    MSG --> GT
```

---

## 2. End-to-End Flow (Main Flowchart)

```mermaid
flowchart TD
    S([Start]) --> U[Citizen uploads documents<br/>PDF / JPG / PNG / TIFF]
    U --> V{Validate file<br/>header bytes + decode}
    V -- invalid --> X[Reject with plain message]
    V -- valid --> ST[Store original in Blob<br/>SHA-256 hash, immutable]
    ST --> Q[Queue: extraction_queue]
    Q --> OCR[OCR reads text]
    OCR --> EXT[LLM extracts 9 identity fields<br/>name, parent, DOB, gender,<br/>address, income, ID no...]
    EXT --> LOC[Locate each value on page<br/>for highlighting]
    LOC --> ALL{All documents<br/>in bundle done?}
    ALL -- no --> W[Wait for others]
    W --> ALL
    ALL -- yes --> CMP[Cross-document comparison engine<br/>every pair, every field]
    CMP --> CL{Difference<br/>found?}
    CL -- no --> M[Match]
    CL -- yes --> RS{Named harmless<br/>reason exists?}
    RS -- yes --> H[HARMLESS<br/>ignored, shown as info]
    RS -- no --> CF[CONFLICT<br/>severity + location + message]
    M --> PR
    H --> PR
    CF --> PR[Build verified profile]
    PR --> REV[Reviewer / Family Head:<br/>accept or dismiss each finding,<br/>choose authoritative value]
    REV --> FORM[Auto-fill official forms<br/>from verified profile]
    FORM --> E([End])
```

---

## 3. Comparison Engine Decision Logic (the key slide for judges)

```mermaid
flowchart TD
    A[Two values of the same field<br/>from two documents] --> B{Field type}
    B -- Name --> N1[Lowercase, remove honorifics<br/>Shri / Smt / Dr]
    N1 --> N2[Align name parts]
    N2 --> N3{Relation of parts}
    N3 -- exact --> OK1[Match]
    N3 -- initial A. = Ajay --> H1[Harmless: initials]
    N3 -- Mohd = Mohammad --> H2[Harmless: abbreviation]
    N3 -- same sound<br/>Sunita = Suneeta --> H3[Harmless: spelling variant]
    N3 -- Hindi vs English --> H4[Harmless: transliteration]
    N3 -- extra middle name --> H5[Harmless]
    N3 -- one-letter slip<br/>Verma / Varma --> C1[Conflict: MEDIUM<br/>possible spelling error]
    N3 -- completely different<br/>Rahul / Sanjay --> C2[Conflict: CRITICAL<br/>different name]
    B -- Date of birth --> D1{Compare}
    D1 -- different year --> C3[HIGH]
    D1 -- day/month swapped --> C4[LOW]
    D1 -- one digit off --> C5[MEDIUM]
    B -- Gender --> G1[Different = HIGH]
    B -- Income --> I1{Ratio higher/lower}
    I1 -- up to 1.01 --> OK2[Match]
    I1 -- under 1.25 --> C6[MEDIUM]
    I1 -- under 2 --> C7[HIGH]
    I1 -- 2 or more --> C8[CRITICAL]
    B -- ID number --> ID1[Remove separators,<br/>masked X * # match anything]
    ID1 --> C9[Different = HIGH]
    B -- Address --> AD1[Expand abbreviations rd, st, nr]
    AD1 --> AD2{Postal code same?}
    AD2 -- no --> C10[MEDIUM locality difference]
    AD2 -- yes --> AD3{Leftover words?}
    AD3 -- none --> H6[Harmless: formatting]
    AD3 -- only numbers --> C11[LOW]
    AD3 -- other words --> C10
```

---

## 4. Harmless vs Real Conflict (simple slide for non-technical audience)

```mermaid
flowchart LR
    subgraph Harmless["IGNORED - harmless"]
        h1["Sunita Choudhary<br/>= Suneeta Chowdhary"]
        h2["A. P. Sharma<br/>= Ajay Prakash Sharma"]
        h3["Hindi name<br/>= English name"]
        h4["Mohd = Mohammad"]
        h5["Rd = Road"]
    end
    subgraph Real["FLAGGED - real conflict"]
        r1["DOB 15 years apart<br/>HIGH"]
        r2["Rahul Verma<br/>vs Sanjay Singh<br/>CRITICAL"]
        r3["Income 60,000<br/>vs 4,80,000<br/>CRITICAL"]
        r4["Gender mismatch<br/>HIGH"]
        r5["Verma vs Varma<br/>MEDIUM - human decides"]
    end
    ENGINE{{"Rule: harmless ONLY if a<br/>named reason explains it<br/>(not just high similarity score)"}}
    ENGINE --> Harmless
    ENGINE --> Real
```

---

## 5. Sequence Diagram (what happens on upload)

```mermaid
sequenceDiagram
    actor User as Citizen
    participant FE as React Frontend
    participant API as FastAPI
    participant BL as Blob Storage
    participant RD as Redis Queue
    participant EX as Extraction Worker
    participant OCR as OCR + LLM
    participant FW as Forensics Worker
    participant DB as PostgreSQL
    User->>FE: Select documents
    FE->>API: POST /cases (documents)
    API->>API: Validate type, size, decode
    API->>BL: Save original (SHA-256)
    API->>DB: Create case + document rows
    API->>RD: Enqueue process_document
    API-->>FE: Case created (processing)
    RD->>EX: process_document
    EX->>OCR: Read text, extract identity fields
    OCR-->>EX: Structured JSON
    EX->>DB: Save fields + value locations
    EX->>RD: Enqueue run_cross_document_checks
    RD->>FW: run_cross_document_checks
    FW->>DB: Read all docs of the case
    FW->>FW: Compare every pair of documents
    FW->>DB: Save findings (severity, reason, evidence)
    FE->>API: GET /cases/id?lang=hi
    API-->>FE: Findings + plain-language messages
    User->>FE: Accept / dismiss finding
    FE->>API: PATCH /cases/id/findings/fid
    API->>DB: Save decision + audit event
```

---

## 6. Severity Levels

```mermaid
flowchart LR
    I[INFO<br/>harmless difference] --> L[LOW<br/>day/month swap,<br/>number-only address diff]
    L --> M[MEDIUM<br/>one-letter name slip,<br/>one-digit date, locality]
    M --> Hh[HIGH<br/>different year, gender,<br/>ID number, income 1.25-2x]
    Hh --> Cr[CRITICAL<br/>different person,<br/>income 2x or more]
    style I fill:#d1fae5,stroke:#059669
    style L fill:#fef9c3,stroke:#ca8a04
    style M fill:#fed7aa,stroke:#ea580c
    style Hh fill:#fecaca,stroke:#dc2626
    style Cr fill:#fca5a5,stroke:#991b1b
```

---

## 7. Data Model (ER Diagram)

```mermaid
erDiagram
    COMPANY ||--o{ USER : has
    COMPANY ||--o{ CASE : owns
    COMPANY ||--o{ FAMILY : has
    FAMILY ||--o{ FAMILY_MEMBER : contains
    USER ||--o{ CASE : submits
    FAMILY_MEMBER ||--o{ CASE : "bundle of"
    CASE ||--o{ DOCUMENT : contains
    CASE ||--o{ CROSS_DOCUMENT_FINDING : produces
    DOCUMENT ||--o{ DOCUMENT_CHECK : "forensic checks"
    CASE ||--o{ AUDIT_LOG : "append-only"
    BULK_UPLOAD ||--o{ CASE : creates
    COMPANY {
        string name
        string subdomain
    }
    USER {
        string email
        string role
    }
    CASE {
        string case_type
        json profile_overrides
        string status
    }
    DOCUMENT {
        string doc_type
        json identity_fields
        string sha256
    }
    CROSS_DOCUMENT_FINDING {
        string field
        string classification
        string reason
        string severity
        string review_state
    }
    FAMILY_MEMBER {
        string relation
        date date_of_birth
    }
```

---

## 8. Multi-Tenancy and Roles (Security Slide)

```mermaid
flowchart TD
    REQ[Request with JWT + optional<br/>X-Org-Subdomain header] --> AUTH{Token valid?}
    AUTH -- no --> E401[401 - same error for wrong<br/>password or wrong org]
    AUTH -- yes --> CO[Session bound to token's company_id]
    CO --> ORM[ORM auto-filters by company_id]
    ORM --> RLS[PostgreSQL Row-Level Security<br/>second wall of defence]
    RLS --> RBAC{Role}
    RBAC --> U[user / citizen<br/>own cases only]
    RBAC --> FH[family head<br/>manages members]
    RBAC --> R1[reviewer L1<br/>review findings]
    RBAC --> R2[reviewer L2<br/>escalations]
    RBAC --> PA[platform admin<br/>no company, manages tenants]
```

---

## 9. Verification Modes (Bulk Upload)

```mermaid
flowchart TD
    Z[Upload ZIP<br/>one folder per person] --> MODE{Choose verification mode}
    MODE -- Cross-Document --> M1[Extract + contradiction check<br/>across the bundle]
    MODE -- Forensics only --> M2[Tampering / metadata /<br/>font / ELA per document]
    MODE -- Both 360 degree --> M3[Contradiction check<br/>+ forensics on each card]
    M1 --> OUT[Cases created, one per folder,<br/>tracked on Bulk Upload dashboard]
    M2 --> OUT
    M3 --> OUT
```

---

## 10. Multilingual Message Pipeline

```mermaid
flowchart LR
    F[Finding<br/>field + reason + values] --> T[Fixed template<br/>what differs / why / what to do]
    T --> L{Language}
    L -- English --> EN[Built-in]
    L -- Hindi --> HI[Hand-written, built-in<br/>no API key needed]
    L -- 11 other Indian languages<br/>+ Urdu RTL --> GT[Google Cloud Translation<br/>TEMPLATES ONLY]
    EN --> FILL
    HI --> FILL
    GT --> FILL[Fill person's details AFTER translation]
    FILL --> OUT[Plain message shown to user]
    note["Privacy: personal details are never<br/>sent to the translation service"]
    GT -.- note
```

---

## 11. Family Verification Flow

```mermaid
flowchart TD
    H[Family Head creates family] --> AM[Add members: spouse, child, parent]
    AM --> UP[Upload documents per member]
    UP --> PROF[Each member gets a verified profile]
    PROF --> FC[Family-level checks<br/>computed on every read]
    FC --> C1[member identity matches entered details]
    FC --> C2[shared address consistent]
    FC --> C3[parent name matches parent's own profile]
    FC --> C4[birth order consistent]
    C1 --> RES{Result}
    C2 --> RES
    C3 --> RES
    C4 --> RES
    RES --> MA[match]
    RES --> CO[conflict]
    RES --> NC[not_checked<br/>detail missing or still disputed]
```

---

## 12. Verified Profile and Form Auto-fill

```mermaid
flowchart LR
    D1[Aadhaar-like card] --> P
    D2[PAN-like card] --> P
    D3[Address proof] --> P
    D4[Income certificate] --> P
    P[Profile builder<br/>per detail] --> ST{Status}
    ST --> AG[agreed]
    ST --> CF[conflict -> user picks document]
    ST --> CH[chosen]
    ST --> MI[missing]
    AG --> PV[Verified Profile]
    CH --> PV
    CF -.-> FIX[Tells which document<br/>probably needs correcting]
    PV --> FR[Sample forms<br/>income certificate, scholarship,<br/>domicile, employee joining]
    FR --> FS[Field status:<br/>filled / needs_attention / to_fill]
```

---

## 13. Technology Stack

```mermaid
flowchart TB
    subgraph FE[Frontend]
        a1[React + TypeScript]
        a2[Vite + Tailwind + shadcn/ui]
        a3[TanStack Query + Zod]
    end
    subgraph BE[Backend]
        b1[FastAPI + SQLAlchemy + Alembic]
        b2[Celery + Redis]
        b3[rapidfuzz + PyMuPDF + Pillow]
    end
    subgraph DB[Data]
        c1[PostgreSQL + RLS + PgBouncer]
        c2[Blob Storage]
    end
    subgraph AI[AI / Cloud]
        d1[OCR: Document Intelligence]
        d2[LLM: Azure OpenAI / Groq]
        d3[Google Cloud Translation]
    end
    subgraph OPS[Ops]
        e1[Docker Compose]
        e2[Pytest ~1000 tests]
        e3[Playwright E2E]
    end
    FE --> BE --> DB
    BE --> AI
    OPS -.-> BE
```

---

## 14. Project Timeline / Phases

```mermaid
flowchart LR
    P1[Phase 1<br/>Intake + extraction] --> P2[Phase 2<br/>16 synthetic bundles]
    P2 --> P3[Phase 3<br/>Comparison engine]
    P3 --> P4[Phase 4<br/>Review + 13 languages]
    P4 --> P6[Phase 6<br/>Profile + forms]
    P6 --> P5[Phase 5<br/>Family]
    P5 --> P7[Phase 7<br/>Subdomain per org]
    P7 --> P8[Phase 8<br/>Report + demo]
    P8 --> P9[Extras<br/>Self-register, bulk modes,<br/>citizen self-review]
```

---

## Suggested PPT slide order

1. Problem statement (PRAGATI02) - text
2. Solution overview - Diagram 4
3. Architecture - Diagram 1 (or 13 for the tech stack)
4. How it works - Diagram 2
5. Core innovation - Diagram 3 + Diagram 6
6. Upload sequence - Diagram 5
7. Reviewer + multilingual - Diagram 10
8. Family + forms - Diagrams 11 and 12
9. Security and multi-tenancy - Diagram 8 (and 7 if technical judges)
10. Bulk upload - Diagram 9
11. Demo results: 16 bundles, 42 documents, 11 conflicts flagged, 24 harmless ignored (a consistency check, not an accuracy claim)
12. Roadmap - Diagram 14 and the not-yet-built list

Honest note for slides: the 35/35 result is a consistency check against ground truth written by the same author, not an accuracy measurement.
