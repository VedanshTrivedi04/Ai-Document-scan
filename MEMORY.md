# MEMORY — Project Context for Any Agent Picking This Up

Written 9 October 2026 from the full working session that built this. Read
this first. It records what the project is, what the owner asked for, what was
researched, every decision and the reason for it, what exists now, what has
not been verified, and what is still open.

Facts here were checked against the repository on the date above unless marked
"not verified". If the code disagrees with this file, the code is right:
update this file.

Related files:

| File | Use it for |
| --- | --- |
| [docs/DEVELOPMENT_PHASES.md](docs/DEVELOPMENT_PHASES.md) | What each phase built and its API contract (keep this current) |
| [docs/FRONTEND_PROMPTS.md](docs/FRONTEND_PROMPTS.md) | The exact briefs given to the frontend agent, phase by phase |
| [docs/CONTRADICTION_DETECTOR_REPORT.md](docs/CONTRADICTION_DETECTOR_REPORT.md) | The short report for judges, with the architecture diagram |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | How to present it |
| [docs/TESTING_CHECKLIST.md](docs/TESTING_CHECKLIST.md) | Every feature with its checks and expected results |
| [docs/FEATURE_TESTING_WORKFLOW.docx](docs/FEATURE_TESTING_WORKFLOW.docx) | The same as a step-by-step Word file, in Hinglish, for the owner's tester |
| [docs/CONTRADICTION_DETECTOR_PLAN.md](docs/CONTRADICTION_DETECTOR_PLAN.md) | The design written before development (historical) |
| [SPECIFICATION.md](SPECIFICATION.md), [docs/README.md](docs/README.md) | The original platform (FDDT) this is built on |

---

## 1. One-paragraph summary

The repository began as **FDDT (Fraud Document Detection Tool)**, a
multi-tenant platform that checks invoices and similar claim documents for
forgery. The owner entered a hackathon with the problem statement **PRAGATI02:
AI-Based Document Contradiction Detector for Public Systems** and chose to
build the answer inside this same repository. Over eight phases the backend
gained: intake of a person's document bundle (PDF and images), extraction of
the person's details, a rule-based engine that separates harmless differences
from real conflicts, per-finding review, messages in 13 languages, a verified
profile, form auto-fill, family management with family-level checks, and one
site per organisation by subdomain. A separate frontend agent built the screens
from briefs written after each backend phase. Nothing has yet been run against
the real cloud services.

---

## 2. The owner and how they work

- Name on the git account: VedanshTrivedi04. Based in Indore, India.
- Writes in **Hinglish** (Hindi in Latin script mixed with English), with many
  typos. Reply in the same register. Documents meant for judges, testers or
  other developers are written in plain English.
- Is taking part in a hackathon. The deadline was described as "tonight" on
  8 October 2026. Whether the submission has happened is not known.
- Wants **phase-by-phase** work: plan first, then build one phase, report, wait
  for "go" before the next.
- Runs **two agents**: this one does the backend only; a second agent does the
  frontend. After each backend phase the owner wants a ready-to-paste **prompt
  for the frontend agent** containing the API contract and a concrete UI idea.
- Insists that **all testing uses fake data**. No real person's documents.
- Wants messages an ordinary person understands, not technical wording.
- Often says "do not implement yet, only plan". Respect that literally.
- Has no Azure account or keys at present (see Section 12).

---

## 3. The problem statement (as the owner pasted it)

> **AI-Based Document Contradiction Detector for Public Systems**
> Find conflicts across a citizen's documents.
>
> **Detailed description.** Citizens submit several documents for one
> application, such as ID, address proof and income certificate. Differences
> in names, dates or addresses cause rejections and delays, and checking them
> by hand is slow.
>
> **Objective.** Build an AI tool that finds conflicting information across a
> citizen's documents and explains each conflict.
>
> - Reads PDFs and images with OCR.
> - Ignores harmless spelling differences.
> - Flags real conflicts with severity and exact location.
> - Reviewer accepts or dismisses each finding.
>
> **Key features.** Read PDFs and images with OCR and pull out key details.
> Match across documents, allowing for spelling and transliteration
> differences. Detect true conflicts with severity and exact source location.
> Reviewer screen to accept or dismiss findings. Indian-language support
> (bonus). Use synthetic documents only.
>
> **Suggested technology.** OCR, NER, LLM extraction, fuzzy matching, FastAPI,
> React.
>
> **Deliverables.** Detector working on synthetic document bundles. Demo of
> conflicts found and harmless variants ignored. Reviewer screen. Architecture
> diagram, code repository and short report.

---

## 4. How the session went, in order

1. **Analysis of the existing project.** Read `README.md`, `SPECIFICATION.md`
   and the code layout; explained FDDT in technical and non-technical terms.
   A Claude Docs page was also created summarising FDDT (outside the repo).
2. **Owner's first research paste.** A summary from another chat proposing how
   to merge FDDT with the contradiction-detector idea. It had not looked at the
   code and listed most things as "to add". Checked against the code, most
   already existed (Section 5).
3. **The real statement arrived** (Section 3). It was much narrower than the
   pasted summary: no public citizen portal, no notifications, synthetic data
   only.
4. **Owner's wish list:** deadline tonight; edit this project, do not start a
   new one; tenants by subdomain with a separate database schema each; a family
   feature with a head who manages members; automatic filling of official
   forms; suggestions for more add-ons; plan only.
5. **Tenancy decision.** Advised against schema-per-tenant; the owner agreed to
   subdomain plus the existing Row-Level Security (Section 6).
6. **Owner's second research paste**: a long blueprint for the statement
   (Section 5). Compared it line by line with the project.
7. **Owner's further requirements:** the tool must also serve corporate hiring;
   only the head manages the family; messages must be plain; Azure keys would
   come later.
8. **Formal plan document** written (`docs/CONTRADICTION_DETECTOR_PLAN.md`).
9. **Phases 1, 2, 3, 4, 6, 5, 7, 8** built in that order, each followed by a
   frontend prompt (Section 8). The owner chose Phase 6 before Phase 5.
10. **Testing documents:** the checklist, then a feature-wise workflow, then the
    same as a Word file.
11. **Open question when this file was written:** a free substitute for Azure
    (Section 12).
12. Someone (the owner or the other agent) then committed and pushed
    everything: commit `3904c61` on `main`, in sync with
    `origin` (`github.com/VedanshTrivedi04/Ai-Document-scan`).

---

## 5. Research the owner brought, and what was concluded

### 5.1 First paste: "merge plan" from another chat

It proposed two paths (citizens upload their own documents; companies bulk
upload their users' documents), and a table of features marked "ADD": OCR,
Indian language support, NER, fuzzy matching, conflict detection, severity
levels, reviewer dashboard, bulk upload, notifications. Suggested stack
additions: Pytesseract/EasyOCR, Hugging Face NER, FuzzyWuzzy, Redis, Celery.

Checked against the code:

| It said "add" | Reality in FDDT at that time |
| --- | --- |
| OCR | Present: Azure Document Intelligence |
| NER | Present in another form: Azure OpenAI structured extraction |
| Fuzzy matching | Present: rapidfuzz (a better library than FuzzyWuzzy) |
| Conflict detection | Present for amount, date and issuer between invoice documents |
| Severity levels | Present: info, low, medium, high |
| Reviewer dashboard | Present at case level (approve, reject, escalate) |
| Bulk upload | Present: zip, one folder per case |
| Celery and Redis | Present |
| Notifications | Absent, and stated as out of scope in the specification |
| Indian languages | Untested; only English and Arabic had been exercised |

Real gaps identified: a person-centred data model; identity document types
and fields; name, date-of-birth and address comparison; image upload (the
validator was PDF-only on purpose); a decision per finding; a public
self-service path; care with identity data.

### 5.2 Second paste: a full blueprint for PRAGATI02

Useful content adopted:

- The examples of harmless versus real differences (Sunita Choudhary /
  Suneeta Chowdhary; A. P. Sharma / Ajay Prakash Sharma; Hindi against English;
  date of birth one day apart versus 15 years apart; Rahul Verma / Sanjay
  Singh; income 60,000 against 4,80,000; gender mismatch). These became the
  synthetic bundles.
- **Graded severity for dates** (a one-digit slip is lower than a different
  year). This replaced an earlier idea of treating every date difference as
  high.
- A synthetic data generator as the first module.

Points where the project deliberately differs:

- The blueprint said "score above 85% means harmless". Rejected: "Rahul Verma"
  and "Rohit Verma" score high and are two people. A difference is harmless
  only when a named reason explains it.
- It recommended Double Metaphone. That algorithm is built for English names.
  The engine uses its own sound rules for Indian names instead.
- It promised a report "in 3 seconds". Not promised: the pipeline is queued and
  calls cloud services.
- It recommended PaddleOCR/EasyOCR. The project kept Azure because it was
  already integrated. This is now being reconsidered (Section 12).
- Its market survey (HyperVerge, Karza, IDfy, DigiLocker and their gaps) was
  **not verified** and was left out of the report on purpose.

### 5.3 Add-ons suggested to the owner

Built: telling the applicant which document probably needs correcting (inside
the verified profile). Not built: an application-readiness score, a missing
document checklist per form, validity/expiry alerts, a conflict report PDF,
DigiLocker-style integration, an office-level dashboard, notifications.

---

## 6. Decisions and the reasoning behind them

| Decision | Reason |
| --- | --- |
| Extend FDDT instead of a new project | The owner asked for it, and roughly 70% of what was needed (OCR, extraction, value location, review workflow, audit, tenancy) already existed. The 70% is an estimate, not a measurement. |
| Reuse the `Case` as "one person's bundle" and `cross_document_findings` for the findings | No new core tables; the existing queue, case detail API and highlight mechanism keep working. |
| Two new case types (`identity_verification`, `hiring_verification`) select the new path | Old invoice behaviour stays untouched; the branch is one check on case type. |
| Images allowed only for identity case types | The PDF-only rule existed because FDDT's forensic checks need PDFs. Identity bundles skip forensics. |
| Forensic checks, risk scoring, signature checks kept but skipped for identity cases | Not asked for by the statement; deleting them would break the original product. |
| Comparison is **rules only**, no model call | Same input always gives the same findings; every finding has a named reason; no cost; testable without cloud keys. The plan originally allowed a language-model second opinion for uncertain names; that was not built. |
| Harmless needs a **named reason**, never just a similarity score | See 5.2. This is the main thing judges are expected to probe. |
| One-letter name differences (Verma/Varma, Kiran/Karan) are a `medium` conflict | The rules cannot tell a typo from a different name, so a person decides. |
| Hindi handled by asking extraction for a Latin transliteration and comparing that | Avoids a transliteration library; the comparison tolerates small differences when scripts differ. |
| Messages come from fixed templates, three parts: what differs, why, what to do | Same difference is always described the same way; the owner asked for plain wording. |
| Only templates are translated; a person's details are filled in afterwards | No personal detail is sent to a translation service. There is a test for this. |
| Official Google Cloud Translation API with a key, not a keyless scraping library | The owner asked for "Google translation". Keyless libraries use an unofficial endpoint that can stop working. The call sits behind one function so it can be swapped. |
| Hindi messages hand-written and built in | Hindi (the bonus language) works with no key at all. |
| Subdomain per organisation, **no** schema per organisation | The owner first wanted separate schemas. FDDT's isolation is built on a `company_id` column plus PostgreSQL Row-Level Security across 17 models and 24 migrations, with PgBouncer transaction pooling. Rebuilding that in one night was the largest risk in the plan and the statement does not ask for it. The owner agreed. |
| The subdomain decides whose sign-in page it is; it is not the security boundary | Isolation stays with the token's company and Row-Level Security, so a forged or missing header gains nothing. |
| A wrong-organisation sign-in returns the same 401 as a wrong password | Nothing about other organisations is revealed. |
| Family: only the head manages; members have no sign-in | The owner's explicit choice, and the cheapest to build. |
| Family checks computed on every read, not stored | Simple; they change by themselves when a member's findings are settled. |
| A family check reports `not_checked` when a detail is missing or still disputed | Never guess: a member's own documents are settled first. |
| Profile belongs to a case | Phase 6 was built before Phase 5. A family member's profile is the profile of that member's latest case. |
| Forms are sample forms defined in code | Not copies of any authority's form; no time for a form builder. |
| Generic document names ("identity card", "tax identity card") and "SPECIMEN" on every page | Synthetic data only; nothing imitates a real government document. |
| "Applicant" rather than "citizen" in wording | The owner wants the same tool used for corporate hiring. |

---

## 7. The base platform (FDDT) in brief

- **Backend:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Celery with Redis,
  PgBouncer. Python 3.11+ (developed here on 3.13).
- **Frontend:** React, TypeScript, Vite, Tailwind, shadcn/ui, TanStack Query.
  API base is `/api` through the Vite proxy (which rewrites `Host`).
- **Cloud:** Azure Blob Storage (originals, immutable, SHA-256), Azure Document
  Intelligence (OCR), Azure OpenAI (classification, extraction, vision). All
  behind abstractions: `StorageService`, `OCRService`, `LLMService`.
- **Queues:** `extraction_queue`, `vision_queue`, `forensics_queue`,
  `housekeeping_queue`. `process_document` runs on extraction;
  `run_cross_document_checks` runs on forensics.
- **Tenancy:** every tenant table has `company_id` (`TenantScopedMixin`);
  sessions are bound to a company and filter automatically; PostgreSQL
  Row-Level Security enforces it again. Roles ranked `user` < `reviewer_l1` <
  `reviewer_l2`; `platform_admin` belongs to no company.
- **Rule for any new tenant table:** `TenantScopedMixin`, a `tenant_isolation`
  policy, a `platform_all` policy, explicit grants in its migration, and its
  name added to `TENANT_TABLES` in `backend/tests/test_rls_postgres.py`.
- **Audit:** append-only `audit_log`, written with `record_event`.
- Tests run on in-memory SQLite; cloud services and Celery are stubbed.

---

## 8. What was built, phase by phase

Order of building: 1, 2, 3, 4, 6, 5, 7, 8. Full API contracts are in
`docs/DEVELOPMENT_PHASES.md`.

### Phase 1 — Intake and extraction

- `app/models/case.py`: case types `identity_verification`,
  `hiring_verification`; `IDENTITY_CASE_TYPES`; `is_identity_case_type()`.
- `app/services/upload_validation.py`: `validate_upload(..., allow_images=True)`
  accepts JPEG, PNG, TIFF by header bytes, checks the extension, decodes with
  Pillow.
- `app/services/document_intake.py`: `enqueue_document_pipeline(...,
  forensics=False)` queues extraction only.
- `app/services/identity_documents.py`: the 15 document type labels, the nine
  field names, the stored shape (`schema: "identity"`, `identity_fields`,
  null `core_fields` kept so older readers do not break).
- `app/services/llm_service.py`: `IdentityAnalysis` and field models,
  `_identity_json_schema()`, the identity system prompt,
  `LLMService.extract_identity`.
- `app/tasks/document_processing.py`: identity branch (no line items, no
  multi-invoice, no font check, no `run_document_checks`); triggers the
  case-level check when every document is done.
- `app/services/field_locator_service.py`: locates identity values on the page.
- `app/services/risk_scoring_service.py`: `pipeline_status` does not wait for
  invoice or forensic checks on identity cases.
- Bulk upload and the stuck-document job pass the identity flags through.
- Tests: `tests/test_identity_intake.py`.

### Phase 2 — Synthetic bundles

- `backend/scripts/generate_identity_bundles.py` writes
  `sample-documents/identity-bundles/`: 16 bundles, 42 documents (PDF, JPG,
  PNG, TIFF), `ground_truth.json`, and two zips in bulk-upload layout. About
  5.8 MB. Deterministic.
- Bundles: B01 clean; B02 spelling variants; B03 initials and word order; B04
  name abbreviation; B05 Hindi against English; B06 date of birth one day
  apart; B07 birth year 15 years apart; B08 another person's document; B09
  similar but different name; B10 income eight times higher; B11 gender and
  postal code; B12 image formats; H01 hiring candidate; F01 head, spouse,
  child.
- Pages are drawn with PyMuPDF `insert_htmlbox`, one explicitly placed text box
  per label and value. Two layout bugs were found by looking at the rendered
  pages and fixed: an HTML table made labels and values overlap, and CSS
  letter-spacing broke Devanagari shaping. `garbage=4` on save merges the
  duplicate embedded fonts (file size fell from about 32 MB to 5.8 MB).
- The Hindi document needs a Devanagari font (Nirmala on Windows, Noto
  elsewhere). Without one, B05 is skipped and reported.
- Tests: `tests/test_identity_bundles.py`.

### Phase 3 — Comparison engine

- `app/services/identity_comparison.py`: `compare_names`, `compare_dates`,
  `compare_gender`, `compare_income`, `compare_id_numbers`,
  `compare_addresses`, `find_identity_contradictions`. Details in Section 9.
- `app/models/cross_document_finding.py`: `classification`, `reason`,
  `evidence`, `detail`; severity `critical`.
- `app/tasks/document_checks.py`: `run_cross_document_checks` uses the identity
  engine for identity cases.
- `app/services/field_exception_service.py`: `identity_finding_regions` gives
  the same highlight-region shape the invoice findings use.
- Tests: `tests/test_identity_comparison.py`.

### Phase 4 — Review and languages

- `app/api/findings.py`: `PATCH /cases/{id}/findings/{finding_id}` with
  `accepted`, `dismissed` or `pending` and an optional note. Reviewer roles
  only; refused once the case is decided; audit event `finding_reviewed`.
- `finding_resolution()`: `open`, `conflict_confirmed`, `no_issue`. Dismissing
  a harmless finding means the reviewer treats it as a real conflict.
- Decisions survive a re-run of the check (matched on field, document pair,
  classification and reason).
- `app/services/identity_messages.py`: templates, `build_message` (summary,
  explanation, action, labels), the Hindi catalog.
- `app/services/translation_service.py`: 13 languages (en, hi, mr, gu, bn, pa,
  ta, te, kn, ml, or, as, ur; Urdu is right-to-left), built-in catalogs,
  Google Cloud Translation v2 over `httpx`, memory and Redis cache, a 60-second
  pause after a failure, one warm-up request per case.
- `app/api/i18n.py`: `GET /i18n/languages`, `GET /i18n/catalog`,
  `POST /i18n/translate` (interface strings only; at most 300 strings of 500
  characters).
- `GET /cases/{id}?lang=` returns `message` per finding and `finding_counts`.
- Tests: `tests/test_finding_review_and_i18n.py`.

### Phase 6 — Verified profile and forms (built before Phase 5)

- `app/services/person_profile.py`: per detail `agreed`, `conflict`, `chosen`
  or `missing`; documents grouped by agreement; a majority group names the
  others as `documents_to_correct`. Preference rules: fullest form of a name;
  address proof for the address; most recent income certificate for income.
- `app/services/case_profile.py`: loads a case's profile from stored data.
- `app/services/form_templates.py`: four sample forms (income certificate,
  scholarship, domicile certificate, employee joining). Field status `filled`,
  `needs_attention` or `to_fill`. Age is derived from the date of birth. Hindi
  labels built in.
- `app/api/profiles.py`: `GET /cases/{id}/profile`,
  `PUT /cases/{id}/profile/{field}`, `GET /forms`,
  `GET /cases/{id}/forms/{form_id}`.
- `cases.profile_overrides` stores the reviewer's choices.
- Tests: `tests/test_profile_and_forms.py`.

### Phase 5 — Family

- `app/models/family.py`: `families`, `family_members` (tenant tables with
  Row-Level Security in the migration); `cases.family_member_id`.
- `app/api/families.py`: `GET/POST /family`, `POST /family/members`,
  `PATCH/DELETE /family/members/{id}`, `GET /families/{id}`. Head only for
  changes; reviewers read; everyone else 404; platform admin 403.
- `POST /cases` accepts `family_member_id` (head only, identity types only).
- `app/services/family_checks.py`: `member_identity`, `shared_address`,
  `parent_name`, `birth_order`; results `match`, `conflict`, `not_checked`.
- Tests: `tests/test_family.py`.

### Phase 7 — Subdomain

- `companies.subdomain` (unique). `app/services/subdomains.py`: normalise,
  validate, suggest from a name, reserved labels, and `from_request` (header
  `X-Org-Subdomain`, else `Origin` or `Host` under `APP_BASE_DOMAIN`).
- `app/api/organisation.py`: `GET /organisation` (no sign-in).
- `app/api/auth.py`: sign-in limited to the organisation of the subdomain; a
  token is refused on another organisation's site; `company_subdomain` in the
  login and `/auth/me` responses.
- `app/api/platform.py`: create and update accept `subdomain`.
- Tests: `tests/test_subdomains.py`.

### Phase 8 — Delivery

- The report, the demo script, and `backend/scripts/demo_identity_bundles.py`,
  which runs the detector, profile, forms and family checks on the bundles in a
  terminal with no database, queue or cloud key.

### Migrations added (one chain, head is the last)

`f3b7d1e8a4c5` (previous head) → `a1c5e7f9b3d2` case types → `b2d6f8a0c4e3`
finding fields and `critical` → `c3e7a9b1d5f4` finding review →
`d4f8b0c2e6a5` profile overrides → `e5a9c1d3f7b6` families →
`f6b0d2e4a8c7` company subdomain.

### New settings

`GOOGLE_TRANSLATE_API_KEY`, `GOOGLE_TRANSLATE_TIMEOUT_SECONDS`,
`APP_BASE_DOMAIN` (all in `backend/.env.example`). Frontend:
`VITE_APP_BASE_DOMAIN`.

---

## 9. How the comparison engine decides

Fields compared for every pair of documents in a bundle: full name,
parent/spouse name, date of birth, gender, address, annual income, and ID
number (only between two cards of the same kind).

**Names.** Lower-cased, honorifics removed (shri, smt, mr, dr and others).
Parts are aligned by the strongest relation: exact, abbreviation (mohd / md →
mohammad, kr → kumar, pd → prasad), same sound, initial, one-letter slip.

- Sound key: ordered replacements (chh→ch, sh→s, ph→f, bh→b, dh→d, th→t, kh→k,
  gh→g, jh→j, ee→i, oo→u, ou/ow/au→o, ai/ay→e, ie→i, w→v, z→j, q→k, ck→k,
  x→ks), final y→i, doubled letters collapsed. **Vowels are never dropped**
  (that would merge Rina and Rani). **"aw" is not folded** (it broke Agrawal).
- One-letter slip: at least five letters, same first letter, and either one
  vowel changed, one letter added or dropped, or two neighbours swapped.
- Outcomes: harmless `spelling_variant`, `initials`, `abbreviation`,
  `transliteration`, `honorific_or_word_order`, `extra_middle_name`; conflict
  `different_name` (critical), `possible_spelling_error` (medium),
  `partial_name` (low).

**Dates.** Different year → `date_year_difference` (high). Day and month
swapped → low. One digit different → `date_minor_difference` (medium).
Otherwise `date_difference` (high).

**Gender.** Different → high.

**Income.** Ratio of higher to lower: up to 1.01 match; under 1.25 medium;
under 2 high; 2 or more critical. Different currencies are not compared.

**ID number.** Separators removed; masked positions (X, *, #) agree with
anything; otherwise different → high.

**Address.** Abbreviations expanded (rd, st, nr, mg, mp and others). Different
postal codes → `address_locality_difference` (medium). After that, words one
address has and the other lacks are examined: nothing left on one side →
harmless (`address_formatting`, or `transliteration` across scripts); only
numbers left → `address_difference` (low); other words left → locality
difference (medium).

**Verification.** All 16 bundles give exactly the findings in the ground truth
(35 of 35: 11 conflicts, 24 harmless). The ground truth and the rules have the
same author, so this is a consistency check, not an accuracy measurement. More
than 40 further cases outside the bundles are tested; writing them exposed two
real errors that were fixed (Agrawal/Agarwal judged different people; an
address in another city judged as formatting).

---

## 10. State of the repository when this was written

- Branch `main`, commit `3904c61`, in sync with `origin/main`
  (`github.com/VedanshTrivedi04/Ai-Document-scan`). The only untracked files
  are this one and `docs/FRONTEND_PROMPTS.md`.
- **Backend tests:** 1,034 pass and 1 fails across the whole suite (last full
  run before the commit). The seven new test files were re-run after the
  commit: 207 pass. The one failure,
  `tests/test_signature_task.py::test_signature_comparison_task_flow`, needs
  Azure storage settings and failed before any of this work.
- **Terminal demo** re-run after the commit: 16 bundles, 42 documents, 11
  conflicts flagged, 24 harmless ignored, all as expected.
- `backend/.venv` exists locally (git-ignored). `backend/.env` does **not**
  exist.

### Frontend state (not verified by the backend author)

Present in the commit: `IdentityFindingsPanel`, `PersonDetailsPanel`,
`VerifiedProfilePanel`, `FormsListSection`, `CaseFormPage`, `FamilyPage` and
`components/family/*`, `lib/organisation.ts`, `hooks/useOrganisation.tsx`,
`api/i18n.ts`, `api/profiles.ts`, `api/family.ts`. The `X-Org-Subdomain` header
is referenced in `api/client.ts`. No `LanguageProvider` by that name was found;
how complete the language switching is, is unknown. The frontend has never
been built or run by the backend author.

---

## 11. What has NOT been verified or built

Not verified:

- **Nothing has run against Azure.** Upload, OCR and extraction are tested
  with stand-ins. How well the extraction prompt reads real documents is
  unknown.
- **The six migrations have not been applied** to a running PostgreSQL, and
  the Row-Level Security tests (`tests/test_rls_postgres.py`) have not run for
  the two new tables.
- **Google Translation** has only been exercised against a stand-in.
- The hand-written **Hindi** has not been reviewed by anyone else.
- The **Word file** was not opened and looked at (no LibreOffice; Word
  automation failed on this machine).

Not built:

- Approval is not blocked while findings are open.
- Dates inside messages stay in English form in every language.
- A filled form cannot be saved, submitted or exported.
- The exported case report (PDF) does not list identity findings.
- The case risk badge is not derived from identity findings.
- No language-model second opinion for uncertain names.
- Family checks cannot be accepted or dismissed; a family cannot change its
  head.
- No DNS, TLS or reverse-proxy setup for subdomains; no CORS middleware.
- Notifications, a public self-service portal.

---

## 12. Open item: a free substitute for Azure

The owner's last question: they have no Azure account, so is there a free
substitute that still works properly for testing and for the demo?

Advice given (nothing implemented, waiting for the owner's choice):

| Azure service | Proposed free substitute |
| --- | --- |
| Blob Storage | Azurite, Microsoft's local emulator in Docker (same connection-string approach) |
| Document Intelligence | PyMuPDF text extraction for PDFs that carry text (the synthetic ones do); Tesseract for images, with the Hindi language pack |
| OpenAI extraction | Google Gemini API free tier (structured JSON output); or Ollama with a local model for fully offline use |

Trade-offs stated: free-tier rate limits (process bundles before the demo);
Tesseract must be installed separately on Windows and is weaker on Hindi
images, so B05 is the fragile bundle; Ollama needs a capable laptop and
extracts less well; the old invoice vision checks would not run on these, which
does not affect identity bundles. The current free-tier terms were **not
checked**. An alternative mentioned from memory and also not checked: Azure
for Students credit and the free tier of Document Intelligence.

Two questions were left with the owner: Gemini or Ollama; and whether to add
the three providers behind an `.env` switch so Azure can be restored later.
All three services already sit behind abstractions, so this is new provider
classes plus a setting, not a rewrite. Note `OCRService.analyze_url` takes a
URL; a local OCR provider would read the bytes from storage instead.

---

## 13. Things an agent must know before touching this

- **A live password is in the root `README.md`** (line 137: the admin login for
  an Azure demo deployment). It was there before this work and is now on
  GitHub. The owner was told to remove it and change the password. Do not
  repeat it anywhere.
- **Windows machine.** Shell tools: Git Bash and PowerShell 5.1. Use
  `backend/.venv/Scripts/python`. The system Python lacks the project's
  dependencies.
- **Line endings.** `core.autocrlf` is true; some files are CRLF. Scripted
  edits must preserve the file's existing line endings.
- **Python output encoding** on this console is cp1252: printing Devanagari
  fails unless `PYTHONIOENCODING=utf-8` is set or stdout is reconfigured.
- **Never send a person's details to translation.** Only templates and labels
  go through `translation_service`.
- **Synthetic data only.** Generate, never collect. Keep "SPECIMEN" on pages.
- **Do not overstate.** "35 of 35" is a consistency check. Do not call it
  accuracy. Say plainly that nothing has run on Azure.
- **Do not promise speed.** The pipeline is asynchronous.
- **New tenant table?** Follow the rule in Section 7.
- **Tasks must not hold a database transaction across slow calls**, and must
  write idempotently (FDDT rule).
- **Keep invoice cases working.** Every change branches on the identity case
  types.
- **Commits and pushes** are the owner's call. Ask first.
- A Claude Docs page about FDDT exists outside the repository; it predates the
  contradiction detector and is not maintained.

---

## 14. How to run things

```bash
# from backend/
./.venv/Scripts/python -m pytest                          # all tests
./.venv/Scripts/python -m scripts.demo_identity_bundles   # the detector on every bundle
./.venv/Scripts/python -m scripts.demo_identity_bundles B07 --lang hi
./.venv/Scripts/python -m scripts.demo_identity_bundles H01 --form employee_joining_form
./.venv/Scripts/python -m scripts.demo_identity_bundles F01
./.venv/Scripts/python -m scripts.generate_identity_bundles   # rewrite the sample documents
```

The full application needs Docker (PostgreSQL, Redis, PgBouncer),
`alembic upgrade head`, `python seed.py`, the API, an extraction worker, a
forensics worker, the frontend, and working storage, OCR and extraction
providers. Steps are in `docs/TESTING_CHECKLIST.md` section 0 and
`docs/DEMO_SCRIPT.md`.

---

## 15. Likely next steps

1. Get the owner's answer on Section 12 and add the free providers, then run
   the real pipeline on the synthetic bundles and compare extraction with
   `ground_truth.json`.
2. Apply the migrations to PostgreSQL and run the Row-Level Security tests.
3. Remove the password from `README.md`.
4. Verify the frontend against `docs/TESTING_CHECKLIST.md` section 10.
5. If time allows: block approval while findings are open; include identity
   findings in the exported report; localise dates in messages.

---

## 16. Public Citizen Self-Registration (added 9 October 2026)

### Why it was added

The Family Management and Identity Contradiction Detector features are built
for ordinary citizens and job applicants — not for corporate employees tied
to a company subdomain. Before this change, the only way to create an account
was for a platform admin to log in and call `POST /settings/users`. A citizen
visiting `http://localhost` (or any future public URL) had no way to register
themselves.

### What was built

**Backend — `POST /auth/register`** (`app/api/auth.py`)

- Public endpoint; no bearer token required.
- Accepts `full_name`, `email`, `password` (8–128 chars).
- Looks up the company whose `name` matches `settings.default_company_name`
  (env var `DEFAULT_COMPANY_NAME`, default `"Default Company"`). This company
  already exists: the Alembic multi-tenancy migration creates it from that
  setting.
- Creates a `User` row with `role = "user"` and `company_id` pointing at the
  Default Company. The database CHECK constraint
  `(role = 'platform_admin') = (company_id IS NULL)` is satisfied because the
  new user is a company role with a non-NULL company.
- Row-Level Security works unchanged: the user's company_id scopes every query
  automatically.
- Returns a `TokenResponse` (same shape as `/auth/login`) so the caller is
  immediately logged in — no extra round-trip.
- `company_subdomain` is always `None` in the response so the frontend does
  NOT redirect the new user to an org subdomain.
- Throttled via the existing `login_throttle.check` IP rate limiter (shares
  the IP ceiling with login; uses the synthetic key `"__register__"` for the
  per-email slot so it never collides with a real email).
- Audit event `user_self_registered` is recorded.

**New schema** (`app/schemas/auth.py`) — `RegisterRequest` model.

**Frontend — `api/auth.ts`**

- New `RegisterPayload` interface and `register()` function calling
  `POST /auth/register`.

**Frontend — `hooks/useAuth.tsx`**

- `register` callback added (parallel to `login`). Both share a private
  `_storeToken` helper that writes to `localStorage` and sets the React state.
- `AuthContextValue` and the provider's `useMemo` value updated accordingly.

**Frontend — `pages/LoginPage.tsx`** (full rewrite of the file)

- Sign In / Sign Up **tab switcher** added (shown only when `isOrgSite` is
  false, i.e. on `localhost` and any public URL without an org subdomain).
  On an organisation's subdomain only the Sign In form is shown — citizens
  on a company portal must be created by a company admin.
- Sign Up form: Full Name, Email, Password, Confirm Password with Zod
  validation (password ≥ 8 chars, passwords must match).
- After successful registration the user is navigated to `/family` — the
  citizen's primary destination.
- "New here? Create a free account" link on the Sign In form and "Already
  have an account? Sign in" link on the Sign Up form cross-navigate the tabs.
- No breaking changes to the existing Sign In form (same fields, same IDs,
  same redirect logic for org subdomain users).

### What did NOT change

- No new migration. The Default Company and the database constraint were
  already there.
- Invoice cases, reviewer workflows, platform-admin screens — unaffected.
- RLS isolation is unchanged. Self-registered citizens see only the Default
  Company's data, and only their own cases (company-level RLS + the
  `submitted_by_user_id` filter in the cases API).
- The platform admin can still create users by hand as before.

### Important constraints carried forward

- The Default Company must exist and be active. If a platform admin deletes
  or suspends it, `/auth/register` returns 503 with a user-readable message.
- Self-registered users cannot change their own company. They are permanently
  in the Default Company unless a platform admin moves them.
- Password reset is still done by a platform admin (no email-based reset was
  added). This is a known limitation.

---

## 17. Citizen Self-Review & Company Reviewer Separation (added 9 October 2026)

### Why it was changed

Previously, every case (even personal/family identity bundles submitted by a
normal citizen on `localhost`) displayed the corporate `CaseDecisionPanel`
("Review status: Your case is with the review team", plus Approve/Reject/Escalate
buttons). Furthermore, when documents in an identity case had contradictory details
(e.g. name or DOB mismatch), resolving the disputed value via
`PUT /cases/{id}/profile/{field_name}` strictly required a corporate `reviewer_l1`
or `reviewer_l2` role, meaning ordinary citizens/family heads could not resolve
their own household discrepancies.

### What was built

1. **Backend Profile Resolution Permissions** (`backend/app/api/profiles.py`):
   - `PUT /cases/{case_id}/profile/{field_name}` updated to allow either:
     - A corporate reviewer (`has_rank(actor.role, 'reviewer_l1')`), OR
     - The **Family Head / Submitter** (`case.submitted_by_user_id == actor.id`).
   - Normal citizens can now choose and resolve contradictory profile fields for
     their own cases and family members without needing a corporate reviewer.

2. **Frontend Reviewer Controls Cleanup** (`frontend/src/pages/CaseDetailPage.tsx`):
   - **`CaseDecisionPanel` hidden for regular citizens:** The corporate review
     actions (Approve/Reject/Escalate and "Waiting for review team" banner) are now
     only displayed when on a corporate organisation subdomain (`isOrgSite`) or
     when the logged-in user possesses a corporate reviewer role (`reviewer_l1`/`reviewer_l2`).
   - **Family Head Enabled:** `VerifiedProfilePanel` receives `canAct = caseDetail?.can_act || isFamilyHead`.
     Family Heads can click "Use this" / "Change" to pick the authoritative document
     when conflicts arise across identity proofs.
   - **Breadcrumb Navigation:** On citizen identity cases, the top link navigates
     directly to `Back to family` (`/family`) or `Back to my cases` (`/my-cases`)
     instead of the corporate reviewer queue.

3. **Navigation Bar Scoping** (`frontend/src/design-system/Nav.tsx`):
   - For regular citizens on `localhost`: Primary navigation links are **"My family"**,
     **"My cases"**, and **"Dashboard"**.
   - The company review queue link (**"Cases"**) is scoped to corporate reviewers
     and users accessing via company subdomains.

---

## 18. Profile-Centric Document Appending & Cross-Document Verification (added 9 October 2026)

### Why it was changed

Previously, whenever a citizen user navigated to `/cases/new` (or clicked "New upload")
to upload an additional document (e.g. uploading a PAN card after previously uploading an Aadhaar card),
the submission form invoked `createCase(...)` which generated an isolated new `Case` record each time.
Because cross-document contradiction checks only execute across documents sharing the *same* case ID
(`Document.case_id == Case.id`), having one document per case meant cross-document analysis never executed,
preventing the system from flagging inconsistencies between Aadhaar, PAN, voter cards, etc.

### What was built

1. **Automatic Bundle Connection in Intake** (`frontend/src/pages/NewCasePage.tsx`):
   - When a citizen or family head submits person documents (`submissionCategory === "person"` and
     `case_type === "identity_verification"`), the page detects if an active identity case already exists
     for that person (from `selectedMember.latest_case_id`, `familyData` self member, or `listCases`).
   - If an existing profile bundle exists, the upload attaches directly to that existing case ID instead
     of creating a duplicate disconnected case.
   - A clear banner notifies the citizen: *"Connecting to your active profile (CASE-XXXX). Any new document
     you upload will be automatically added to this person's bundle. All your documents will be cross-analyzed
     together to detect inconsistencies in name, DOB, address, or parent names."*
   - Citizens can still click *"Create separate bundle instead"* if they explicitly wish to isolate a profile.

2. **In-Profile Direct Upload Tab** (`frontend/src/pages/CaseDetailPage.tsx`):
   - A dedicated `+ Add document to profile` button on the document tab bar allows citizens to directly
     upload further credentials (PAN, Aadhaar, Driving Licence, etc.) straight into their bundle.
   - When a new document finishes processing, Celery task `run_cross_document_checks` triggers across all
     completed documents in the case, comparing names, dates of birth, addresses, and ID numbers.

---

## 19. Comprehensive End-to-End (E2E) Verification with Playwright (added 9 October 2026)

### What was tested and verified across portals:

1. **Citizen Onboarding & Household Creation (`localhost`):**
   - New citizen account creation via public registration tab (`POST /auth/register`).
   - Setup of household via `/family` (`POST /family`), correctly assigning citizen as household head.

2. **Multi-Document Profile Appending & Cross-Document Contradiction Detection:**
   - Intake of initial Aadhaar card (Name: *Rahul Sharma*, DOB: *15/08/1990*).
   - In-profile direct upload (`+ Add document to profile`) of PAN card with deliberate discrepancy (DOB: *15/08/1991*).
   - Celery async worker executed pairwise OCR & `identity_consistency` contradiction engine.
   - **Result:** Contradiction detected immediately:
     > *"Date of birth does not match: 15 August 1990 on the identity card and 15 August 1991 on the tax identity card (The years are 1 year apart)."*

3. **Citizen Self-Resolution Without Corporate Blockers:**
   - Citizen clicked "Use this" to choose the authoritative DOB (*15 August 1990*).
   - `PUT /cases/{id}/profile/date_of_birth` succeeded (with fixed `has_rank` import).
   - Profile automatically transitioned to **Profile ready** with the selected value marked as chosen.
   - On `/family`, the household verification check transitioned from *Not checked* to **1 Match** (*"Rahul Sharma: the documents match the details entered for this family member."*).

4. **Corporate Reviewer Hierarchy & Decision Auditing:**
   - Logged in as corporate reviewer (`reviewer1@example.com`).
   - Active Case Queue displayed prioritized triage list with flags and metrics.
   - Reviewer opened case, inspected documents, and approved the case.
   - Status updated to **Approved** and immutable audit log captured every step (`case_created` → `document_uploaded` → `cross_document_check_completed` → `profile_value_chosen` → `case_approved`).

5. **Operational Dashboard & Priority Queue (`/dashboard`):**
   - KPI cards accurately rendered real-time stats (6 documents across 5 cases).
   - Risk tier distribution chart and priority triage queue listed open pending cases.

6. **Append-Only Compliance Audit Trail (`/audit-history`):**
   - Verified that every single actor, action (`case_approved`, `profile_value_chosen`, `document_uploaded`, `case_created`, etc.), timestamp, and case reference are strictly preserved and searchable.

7. **Pre-filled Application Forms (`/forms/income_certificate_application`):**
   - Automated pre-filling verified: 5 of 10 fields filled directly from verified documents (Full name, DOB, Address, Postal code, ID number) with lock indicators, allowing the applicant to supply missing fields (Father's name, Gender, Annual income).

8. **RBAC & Multi-Tenant Route Guard Enforcement:**
   - Tested accessing platform superadmin routes (`/platform/companies`) while logged in as a company Reviewer L1.
   - Verified that route was blocked with clear access restriction message (*"Platform admin access required. Your account (Reviewer L1 role) doesn't have access to this page."*).

9. **Platform Superadmin Administration & Celery Queues (`/platform/companies`, `/platform/queues`):**
   - Logged in as Superadmin (`admin@example.com`).
   - Verified tenant company management table across companies, site addresses, upload limits, and suspension controls.
   - Verified real-time Celery queue metrics on `/platform/queues`:
     - `extraction_queue` (Azure Document Intelligence): **Healthy** (0 waiting, 0 running, avg wait 0.0s).
     - `vision_queue` (Azure OpenAI): **Healthy**.
     - `forensics_queue` (Local CPU): **Healthy** (0 waiting, avg wait 0.1s).




