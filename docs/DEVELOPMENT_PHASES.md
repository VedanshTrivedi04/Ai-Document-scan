# Development Phases — Document Contradiction Detector

Feature description: [CONTRADICTION_DETECTOR_PLAN.md](CONTRADICTION_DETECTOR_PLAN.md).
Backend is built phase by phase; each phase ends with a frontend brief for the
same phase. All tests and demo data use made-up people only.

| Phase | Scope | Required by the problem statement | Status |
| --- | --- | --- | --- |
| 1 | Intake and extraction for identity bundles | Yes | Done (backend) |
| 2 | Synthetic bundle generator | Yes | Done |
| 3 | Comparison engine and findings | Yes | Done (backend) |
| 4 | Finding review and messages in several languages | Yes | Done (backend) |
| 5 | Family management and family-level checks | No | Done (backend) |
| 6 | Verified profile and form auto-fill | No | Done (backend) |
| 7 | Organisation by subdomain | No | Done (backend) |
| 8 | Architecture diagram, report, demo script | Yes | Done |

If time runs short, phases 5, 6 and 7 are dropped first.

---

## Phase 1 — Intake and extraction (done)

**Backend**

- Two case types: `identity_verification`, `hiring_verification`
  (`app/models/case.py`; migration `a1c5e7f9b3d2`).
- A case of either type accepts JPEG, PNG and TIFF as well as PDF
  (`app/services/upload_validation.py`, `allow_images`). Other case types are
  unchanged: PDF only.
- Only extraction is queued for such a case; the forensic tasks are skipped
  (`app/services/document_intake.py`).
- `LLMService.extract_identity` classifies the document and extracts the
  person's details (`app/services/llm_service.py`,
  `app/services/identity_documents.py`).
- Each extracted value is located on the page
  (`app/services/field_locator_service.py`).
- The case completes without the invoice checks
  (`app/services/risk_scoring_service.py`, `pipeline_status`).
- Tests: `tests/test_identity_intake.py`.

**API contract**

- `POST /cases` accepts `case_type: "identity_verification" | "hiring_verification"`.
- `POST /cases/{id}/documents` on such a case accepts `image/jpeg`, `image/png`, `image/tiff`.
- `GET /cases/{id}` → each document's `extracted_fields`:

```json
{
  "schema": "identity",
  "document_type_confidence": 0.95,
  "identity_fields": {
    "full_name":             {"value": "...", "latin": "...", "confidence": 0.9, "uncertain": false, "bounding_box": {"page": 1, "x": 0.1, "y": 0.15, "width": 0.3, "height": 0.02}},
    "parent_or_spouse_name": {"value": "...", "latin": "...", "confidence": 0.9, "uncertain": false},
    "date_of_birth":         {"value": "1991-04-12", "raw_text": "12/04/1991", "confidence": 0.9, "uncertain": false},
    "gender":                {"value": "female", "raw_text": "Female", "confidence": 0.9, "uncertain": false},
    "address":               {"value": "...", "latin": "...", "postal_code": "452001", "confidence": 0.9, "uncertain": false},
    "id_number":             {"value": "XXXX XXXX 4321", "confidence": 0.9, "uncertain": false},
    "annual_income":         {"value": 120000, "currency": "INR", "raw_text": "Rs. 1,20,000", "confidence": 0.9, "uncertain": false},
    "issuing_authority":     {"value": "...", "confidence": 0.8, "uncertain": false},
    "issue_date":            {"value": "2026-01-10", "raw_text": "10-01-2026", "confidence": 0.9, "uncertain": false}
  },
  "core_fields": { "...": "all values null for identity documents" },
  "additional_fields": []
}
```

`bounding_box` is present only when the value was found on the page; all
coordinates are fractions (0–1) of the page.

`document_type` is one of: `national_id_card`, `tax_id_card`, `voter_id_card`,
`driving_licence`, `passport`, `birth_certificate`, `income_certificate`,
`address_proof`, `caste_certificate`, `domicile_certificate`, `marksheet`,
`degree_certificate`, `experience_letter`, `payslip`, `other`.

---

## Phase 2 — Synthetic bundle generator (done)

- `backend/scripts/generate_identity_bundles.py` writes
  `sample-documents/identity-bundles/`: one folder per bundle, a
  `ground_truth.json`, and one zip per case type in the bulk-upload layout.
  Run from `backend/`: `python -m scripts.generate_identity_bundles`.
- Every person, address and number is invented; every page is marked
  "SPECIMEN".
- `ground_truth.json` gives, per document, the correct extraction in the
  Phase 1 `identity_fields` shape, and per bundle the differences a detector
  must ignore (`harmless_variant`) or flag (`conflict`) with reason and
  severity.
- Hindi documents are rendered as images and need a Devanagari font on the
  machine (Nirmala on Windows); without one those bundles are skipped.
- Tests: `tests/test_identity_bundles.py`.
- Frontend: none. `ground_truth.json` can be used as mock case data.

| Bundle | What it tests | Expected |
| --- | --- | --- |
| B01-clean | Everything agrees; only date formats differ | No findings |
| B02-spelling-variants | Sunita Choudhary / Suneeta Chowdhary; M.G. Rd / Mahatma Gandhi Road | Harmless |
| B03-initials-and-order | A. P. Sharma / Ajay Prakash Sharma / Shri Sharma Ajay Prakash | Harmless |
| B04-name-abbreviation | Mohammad / Mohd. / Md | Harmless |
| B05-hindi-transliteration | Hindi identity card (image) against English documents | Harmless |
| B06-dob-minor-typo | Date of birth one day apart | Conflict, medium |
| B07-dob-year-conflict | Birth year 1982 / 1997 | Conflict, high |
| B08-different-person | Rahul Verma / Sanjay Singh | Conflict, critical |
| B09-similar-but-different-name | Rahul Verma / Rohit Verma | Conflict, critical |
| B10-income-conflict | Rs. 60,000 / Rs. 4,80,000 | Conflict, critical |
| B11-gender-and-address | Gender and postal code differ | Conflict, high and medium |
| B12-image-formats | JPG, PNG and TIFF, all agreeing | No findings |
| H01-hiring-candidate | Candidate documents; birth year differs on the degree | Harmless names, conflict high |
| F01-head, F01-spouse, F01-child | A family; the child's marksheet names a different father | Conflict, critical |

## Phase 3 — Comparison engine and findings (done)

**Backend**

- `app/services/identity_comparison.py`: every pair of documents in a bundle
  is compared on name, parent/spouse name, date of birth, gender, address,
  annual income and (between identity cards of the same kind) identity
  number. Rules only, no model call: the same bundle always gives the same
  findings.
- A difference is harmless only when a named reason explains it; a
  similarity score alone never does.
- `app/services/identity_messages.py`: one plain sentence per finding.
- `cross_document_findings` gains `classification`, `reason`, `evidence`;
  severity gains `critical` (migration `b2d6f8a0c4e3`).
- `run_cross_document_checks` uses this engine for identity cases
  (`app/tasks/document_checks.py`).
- Tests: `tests/test_identity_comparison.py`. All 16 synthetic bundles give
  exactly their expected findings.

**Reasons**

| Classification | Reason | Severity |
| --- | --- | --- |
| harmless_variant | `spelling_variant`, `initials`, `abbreviation`, `transliteration`, `honorific_or_word_order`, `extra_middle_name`, `address_formatting` | info |
| conflict | `different_name` | critical |
| conflict | `possible_spelling_error` | medium |
| conflict | `partial_name` | low |
| conflict | `date_year_difference`, `date_difference` | high |
| conflict | `date_minor_difference` | medium |
| conflict | `date_day_month_swapped` | low |
| conflict | `gender_difference`, `id_number_difference` | high |
| conflict | `income_difference` | medium (under 1.25 times), high (under 2 times), critical (2 times or more) |
| conflict | `address_locality_difference` | medium |
| conflict | `address_difference` (house or plot number) | low |

**API contract** — `GET /cases/{id}` → `cross_document_findings[]`, for identity cases:

```json
{
  "id": "…",
  "field_name": "date_of_birth",
  "finding_type": "identity_consistency",
  "classification": "conflict",
  "reason": "date_year_difference",
  "severity": "high",
  "description": "Date of birth does not match: 12 March 1982 on the identity card and 12 March 1997 on the voter identity card. The years are 15 years apart.",
  "document_ids": ["<doc A>", "<doc B>"],
  "evidence": [
    {"document_id": "<doc A>", "document_type": "national_id_card", "document_filename": "01-national-id-card.pdf", "value": "12 March 1982", "bounding_box": {"page": 1, "x": 0.4, "y": 0.3, "width": 0.2, "height": 0.03}},
    {"document_id": "<doc B>", "document_type": "voter_id_card", "document_filename": "03-voter-id-card.pdf", "value": "12 March 1997", "bounding_box": null}
  ],
  "regions": [ { "document_id": "<doc A>", "label": "Date of birth", "value": "12 March 1982", "caption": "…", "other": [ … ], "bounding_box": { … } } ],
  "created_at": "…"
}
```

`regions` has the same shape as for invoice findings, one entry per document
whose value was located. Values that agree produce no finding.

**Not done in this phase**

- Uncertain names are not sent to a language model for a second opinion;
  they are flagged for the reviewer instead.
- The case risk tier is not derived from these findings (it stays "low").
- The exported PDF report does not list identity findings yet.

## Phase 4 — Finding review and messages in several languages (done)

**Backend**

- `PATCH /cases/{id}/findings/{finding_id}` (`app/api/findings.py`): a
  reviewer accepts or dismisses one finding, or sets it back to pending.
  Written to the audit log as `finding_reviewed`. Refused once the case is
  decided. Decisions survive a re-run of the case-level check.
- Each finding has a `resolution`: `open`, `conflict_confirmed` or `no_issue`.
  Dismissing a conflict clears it; dismissing a harmless variant marks it as a
  real conflict. The case carries `finding_counts`.
- Messages (`app/services/identity_messages.py`): every finding has a summary
  (what differs), an explanation (why it matters or not) and an action (what
  to do), plus a severity label in plain words.
- Languages (`app/services/translation_service.py`): English, Hindi, Marathi,
  Gujarati, Bengali, Punjabi, Tamil, Telugu, Kannada, Malayalam, Odia,
  Assamese, Urdu. Hindi finding messages are built in. Everything else is
  translated by Google Cloud Translation when `GOOGLE_TRANSLATE_API_KEY` is
  set, and cached. Without the key those languages fall back to English.
- Only the application's own templates and labels are sent for translation.
  A person's name, date or address is filled in afterwards on the server.
- Migration `c3e7a9b1d5f4`. Tests: `tests/test_finding_review_and_i18n.py`.

**API contract**

- `GET /cases/{id}?lang=hi` → `language`, `finding_counts`
  `{open, conflict_confirmed, no_issue, ignored_as_harmless}`, and on each
  finding: `message {language, field_label, severity_label, summary,
  explanation, action, text}`, `review_status`, `review_note`, `reviewed_at`,
  `reviewed_by_name`, `resolution`.
- `PATCH /cases/{id}/findings/{finding_id}?lang=hi` with
  `{"decision": "accepted" | "dismissed" | "pending", "note": "..."}` →
  `{finding, finding_counts}`. 403 for non-reviewers and for an L1 reviewer on
  an escalated case, 404 unknown case or finding, 409 case already decided.
- `GET /i18n/languages` (no sign-in needed) → `[{code, name, native_name,
  direction, source, available}]`.
- `GET /i18n/catalog?lang=hi` → `{language, direction, fields, documents,
  severities, reasons, actions, no_action}`, keyed by the machine keys.
- `POST /i18n/translate` with `{"language": "mr", "texts": ["My cases"]}` →
  `{language, translations: {english: translated}, complete}`. At most 300
  strings of 500 characters. Interface text only.

**Not done in this phase**

- Approving a case is not blocked while findings are still open.
- Dates inside messages stay in English form ("12 March 1982").
- Google Translation has only been exercised against a stand-in, not the real
  service.

## Phase 5 — Family management (done)

**Backend**

- `families` and `family_members` (`app/models/family.py`), both tenant-owned
  with Row-Level Security policies and grants; `cases.family_member_id`
  (migration `e5a9c1d3f7b6`).
- A user sets up one family and is its head (a member with relation `self`).
  Only the head adds, corrects and removes members and submits a bundle for a
  member (`POST /cases` with `family_member_id`). Members have no sign-in.
- Reviewers of the company can read a family; they cannot change it.
- Family-level checks (`app/services/family_checks.py`), computed from each
  member's latest case and using the same comparison rules as between
  documents: `member_identity` (the documents belong to the person entered),
  `shared_address`, `parent_name`, `birth_order`. Result per check: `match`,
  `conflict` (with severity) or `not_checked` (a detail is missing or still
  disputed in the member's own documents).
- Messages in the Phase 4 languages, Hindi built in.
- Tests: `tests/test_family.py`.

**API contract**

- `GET /family?lang=` → the caller's family, or `null`.
- `POST /family` with `{"name"?, "head_date_of_birth"?}` → 201; 409 if the
  caller already has one.
- `POST /family/members` with `{"full_name", "relation", "date_of_birth"?}`;
  `relation` is `spouse`, `son`, `daughter`, `father`, `mother` or `other`.
- `PATCH /family/members/{id}`, `DELETE /family/members/{id}` (409 for the
  head's own entry and for a member who already has a case).
- `GET /families/{id}?lang=` → the same view, for the head or a reviewer.
- Every one of these returns the family view: `{id, name, head_user_id,
  language, members[], checks[], check_counts {match, conflict,
  not_checked}}`. Member: `{id, full_name, relation, relation_label,
  date_of_birth, is_head, latest_case_id, profile_ready, cases[]}`. Case:
  `{id, case_number, case_type, status, created_at, document_count,
  checks_complete, open_conflicts}`. Check: `{check, label, member_id,
  member_name, relation, result, severity, summary}`.
- `POST /cases` accepts `family_member_id`; `GET /cases/{id}` returns
  `family_member {id, family_id, full_name, relation}`.

**Not done in this phase**

- A reviewer cannot accept or dismiss a family-level check; they are computed
  on every read.
- A family cannot change its head, and a member cannot be moved to a case
  after the case is created.

## Phase 6 — Verified profile and form auto-fill (done)

Built before Phase 5, so the profile belongs to a case (one person's bundle).
When families exist, a member's profile is the profile of that member's case.

**Backend**

- `app/services/person_profile.py`: one final value per detail (name,
  parent/spouse name, date of birth, gender, address, annual income), with the
  document it came from. Status per detail: `agreed`, `conflict`, `chosen`,
  `missing`. A disputed detail has no value; its candidates are listed, and
  when most documents agree the others are named as the ones to correct.
- A reviewer can choose which document is right for a disputed detail
  (`cases.profile_overrides`, migration `d4f8b0c2e6a5`). Clearing the finding
  in Phase 4 has the same effect.
- `app/services/form_templates.py`: four sample forms (income certificate,
  scholarship, domicile certificate, employee joining form). They are written
  for this application, not copies of any authority's form.
- A form field is `filled` (with its source document), `needs_attention`
  (the documents dispute the detail; left empty) or `to_fill` (the applicant
  enters it). Form text is available in the same languages as Phase 4, Hindi
  built in.
- Tests: `tests/test_profile_and_forms.py`.

**API contract**

- `GET /cases/{id}/profile` → `{case_id, case_number, case_type,
  document_count, checks_complete, fields[], postal_code, id_numbers, counts,
  ready}`. Each field: `{field, label, status, value, display_value, latin,
  document_id, document_type, document_filename, candidates[],
  suggested_document_id, documents_to_correct[]}`. 409 for a case that is not
  an identity or hiring case.
- `PUT /cases/{id}/profile/{field}` with `{"document_id": "<id>" | null}` →
  the updated profile. Reviewers only. 422 if the document is not in the case
  or does not state the detail; 409 once the case is decided.
- `GET /forms?case_type=&lang=` → `[{id, title, description, case_types,
  field_count, prefilled_field_count, fields[]}]`.
- `GET /cases/{id}/forms/{form_id}?lang=` → `{case_id, case_number,
  checks_complete, form, language, fields[], counts {filled, needs_attention,
  to_fill}, ready}`. Each field: `{key, label, type, required, prefilled,
  options?, value, display_value, status, note, source_field,
  source_document_id, source_document_type, source_document_filename}`.

**Not done in this phase**

- A filled form is not saved or submitted, and there is no PDF download.
- Forms are defined in code; an organisation cannot add its own.

## Phase 7 — Organisation by subdomain (done)

**Backend**

- `companies.subdomain` (unique; migration `f6b0d2e4a8c7`, which also gives
  every existing company one made from its name).
- `app/services/subdomains.py`: the subdomain a request names comes from the
  `X-Org-Subdomain` header, else the `Origin` or `Host` under
  `APP_BASE_DOMAIN`. Platform labels (`www`, `app`, `api`, `admin`, ...) name
  no organisation.
- Sign-in on an organisation's site is limited to that organisation's users.
  Any other account, including a platform admin, gets the same 401 as a wrong
  password.
- A token is refused (401) on another organisation's site.
- Data isolation is unchanged: the token's company plus Row-Level Security.
  The subdomain only decides whose sign-in page it is. Separate database
  schemas per organisation are not used.
- Platform admins set, change or remove a company's subdomain; a new company
  gets one from its name when none is given.
- Tests: `tests/test_subdomains.py`.

**API contract**

- `GET /organisation` (no sign-in; `?subdomain=`, the header, or the host) →
  `{subdomain, name, base_domain}`. On the platform's own site `subdomain` and
  `name` are null. 404 for a subdomain nobody uses or a suspended organisation.
- `POST /auth/login` honours the request's subdomain and returns
  `company_subdomain` beside the token.
- `GET /auth/me` returns `company_subdomain`.
- `POST /platform/companies` accepts `subdomain` (optional);
  `PATCH /platform/companies/{id}` accepts `subdomain` (empty string or null
  removes it). 409 when taken, 422 when not usable. Company responses include
  `subdomain`.
- Setting: `APP_BASE_DOMAIN` (for local development: `localhost`).

**Not done in this phase**

- No wildcard DNS, TLS certificate or reverse-proxy configuration.
- CORS for `*.<base domain>` is not configured in the API.

## Phase 8 — Delivery (done)

- [CONTRADICTION_DETECTOR_REPORT.md](CONTRADICTION_DETECTOR_REPORT.md): the
  short report, with the architecture diagram, how a difference is judged, the
  results on the synthetic bundles, and what has not been verified.
- [DEMO_SCRIPT.md](DEMO_SCRIPT.md): a terminal demo that needs only Python, and
  a walk through the full application.
- `backend/scripts/demo_identity_bundles.py`: the detector, profile, forms and
  family checks on the synthetic bundles, in a terminal, with no database or
  cloud key.

## Phase 9A — Family member sign-in (done)

A family head can give a member a sign-in. Migration `a8e2c4f6b1d9`
(`family_members.user_id`, `users.must_change_password`).

- `POST /family/members` takes an optional `login: {email, password?}`. Without
  a password a 12-character temporary one is generated. The response is the
  usual family view plus `credentials: {member_id, email, temporary_password}`;
  `temporary_password` is shown once, and is `null` when the head chose it.
- `POST /family/members/{id}/login` (add one to an existing member),
  `POST /family/members/{id}/login/reset-password`,
  `PATCH /family/members/{id}/login` (`{is_active}`),
  `DELETE /family/members/{id}/login` (switches the account off, detaches it).
  Head only; anyone else gets 404. The head's own entry cannot have one (409).
- Each member in the family view has `has_login` and
  `login: {email, is_active, must_change_password} | null`.
- The account is a company user (role `user`) in the head's company, created
  through a platform session because tenant sessions may only read `users`.
  Audit events: `family_member_login_created`, `_password_reset`, `_disabled`,
  `_enabled`, `_removed` (never the password).
- `POST /auth/login` and `GET /auth/me` return `must_change_password`; it is
  cleared by `POST /auth/me/password`.
- A member with a sign-in: `POST /cases` links the case to them automatically
  (identity types) and refuses another member (422); cannot set up a family of
  their own (409); sees no family.
- Removing a member switches their account off. A removed login's email stays
  used by the switched-off account.
- Not yet: the head managing a member's cases and documents (Phase 9B), the
  family comparison case (Phase 9C). A member who is also the submitter can
  still settle conflicts on their own case until 9B restricts that.

## Phase 9B: The head manages members' cases (done)

- `app/api/case_access.py`: a `user` sees the cases they submitted, the cases of a
  family they head (a member's bundle, a comparison), and the cases about
  themselves when they are a member with a sign-in. `can_manage_case`: a
  reviewer, the head of the case's family, or the submitter of a case outside any
  family. A member signed in on their own can see their case but not manage it.
- Head can: upload to a member's case (`POST /cases/{id}/documents`), settle
  profile conflicts (`PUT /cases/{id}/profile/{field}`), accept or dismiss findings
  (`PATCH /cases/{id}/findings/{finding_id}`). Others get 403 (unchanged contract).
- `GET /cases` for a `user` includes the family's cases. `GET /cases/{id}` returns
  `can_manage`.
- `GET /family` lists each case's `documents` ({id, filename, document_type,
  processing_status}). `GET /family/me`: a member's own cases and documents.

## Phase 9C: Family comparison case (done)

Migration `b9f3d5a7c1e2` (`case_type` value `family_comparison`, `cases.family_id`,
`cases.comparison_member_ids`).

- `POST /family/comparisons {member_ids}`: the head is always included; at least
  one other member. Creates a case of type `family_comparison` (no documents) and
  runs the family checks on the members' verified profiles.
- Each conflict is stored as a `cross_document_findings` row (`finding_type`
  `family_check`, `classification` `conflict`, `detail` {member_id, check}), so it
  is accepted or dismissed with `PATCH /cases/{id}/findings/{finding_id}`.
- `GET /family/comparisons` (list), `GET /family/comparisons/{id}?lang=`
  (members, every check with `finding_id`, `review_status`, `resolution`; `is_head`,
  `can_review`), `POST .../refresh` (re-run, keeps decisions on conflicts still
  present, removes those gone), `DELETE` (closes it). Head writes; reviewers read.
- `POST /cases` refuses `family_comparison`; uploading to one is 409.

## Phase 9 frontend (done)

- `pages/ChangePasswordPage.tsx` and a redirect in `ProtectedRoute` for
  `must_change_password`.
- Family page: sign-in controls per member (create, reset, switch off or on,
  remove), one-time credentials dialog, login option in Add member, each case's
  documents, "Add document" (joins the member's existing bundle: `NewCasePage`),
  `FamilyComparePanel`, and `MemberHome` for a member with a sign-in.
- `pages/FamilyComparisonPage.tsx` (`/family/compare/:caseId`); a comparison
  opened as a case redirects there. `CaseDetailPage` follows `can_manage`.
- Checked in a browser against the running stack (16 checks) and by API against
  PostgreSQL (33 checks), and with the real pipeline on the synthetic family F01.

## Phase 10: Document retention and private uploads (done)

Migration `c1a3e5b7d9f2` (`documents.file_deleted_at`, `bulk_uploads.file_deleted_at`,
`cases.delete_on_logout`, `cases.data_removed_at`). Rules and reasons are in
`app/services/retention_service.py`.

**Files expire.** `DOCUMENT_RETENTION_DAYS` (default 24, 0 = off) after upload, a
document's stored file and its OCR text are removed. The extracted details, the
findings, the verified profile and the audit trail stay. The zip of a bulk upload
expires the same way; generated report PDFs do not.

- `StorageService.delete()` (local and Azure; a file already gone is not an error).
- Celery beat: `purge_expired_files` daily at `DOCUMENT_RETENTION_HOUR_UTC`:30,
  `purge_private_cases` every ten minutes, both on `housekeeping_queue`.
- By hand from `backend/`: `python -m scripts.purge_expired_files` counts only;
  `--apply` removes. Removal cannot be undone.
- A document still unread when its file expires is marked `failed`. The stuck-document
  job skips documents without a file.
- API: each document in `GET /cases/{id}` has `file_url` (null once removed),
  `file_deleted_at`, `file_expires_at`. `GET /cases/{id}/documents/{doc}/file-url`
  answers 410 once removed. Family document lists carry `file_deleted`.
  `GET /auth/me/retention` returns `{document_retention_days, private_upload_available}`.
- Audit: `document_file_deleted`, `bulk_upload_file_deleted`.

**Private uploads.** `POST /cases` takes `delete_on_logout: true`, only for a `user` of
the public company on an identity or hiring case (422 otherwise).

- `POST /auth/logout` empties the caller's private cases: files, OCR text, extracted
  details, check results, findings and profile choices; file names become
  "removed document". The emptied case stays, `closed`, with `data_removed_at`.
  Returns `{removed_cases: [case numbers]}`. `GET /auth/private-cases` lists what
  signing out will empty.
- Never signed out: emptied once `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` have passed since
  the case was created. The same job re-empties a case if a document finished
  reading after the wipe.
- An emptied case takes no more uploads (409) and no longer counts as a family
  member's bundle.
- Not removed, because those tables are append-only in the database: audit log
  rows (which include the original file name in `document_uploaded`), case
  actions, risk assessments, generated reports. Signature references are kept.
- Audit: `case_data_removed` (counts and reason only).

**Frontend.** Upload page: a warning that files are removed after N days, and a
"Private upload" toggle (always its own bundle). Case page: "File removed in N days"
beside a stored file, a notice in place of the viewer once it is removed, a banner on
a private case. Sign out asks first when private uploads would be removed.
