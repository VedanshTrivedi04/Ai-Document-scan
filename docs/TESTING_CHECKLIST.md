# Testing Checklist — Document Contradiction Detector

For a developer or tester checking what was built. Each feature lists how to
test it, what should happen, and the automated tests that already cover it.

All test data is in `sample-documents/identity-bundles/`. Every person in it is
invented. `ground_truth.json` there says what each document states and which
findings each bundle should give.

API paths below are the backend's own (`http://localhost:8000`, Swagger at
`/docs`). The frontend calls them under `/api`.

---

## 0. Setup

| Level | What you can test | Needs |
| --- | --- | --- |
| A | Automated tests, terminal demo | Python only |
| B | Every API below except reading real files | Level A + Docker (Postgres, Redis) |
| C | Upload → OCR → extraction → findings, end to end | Level B + Azure keys + workers + frontend |

```bash
# Level A
cd backend
python -m venv .venv && ./.venv/Scripts/activate      # source .venv/bin/activate elsewhere
pip install -r requirements.txt
pytest                                                # expect 1034 passed, 1 failed (see Known issues)
python -m scripts.demo_identity_bundles               # expect every row "as expected"

# Level B
docker compose up -d
cp .env.example .env
alembic upgrade head                                  # six new migrations
python seed.py                                        # admin@example.com / ChangeMe123!
uvicorn app.main:app --reload

# Level C: fill the Azure keys in .env, then
celery -A app.tasks.celery_app worker -Q extraction_queue -n extraction@%h --pool=threads -c 4 --loglevel=info
celery -A app.tasks.celery_app worker -Q forensics_queue,celery -n forensics@%h --pool=threads -c 4 --loglevel=info
cd ../frontend && npm install && npm run dev          # http://localhost:5173
```

**Accounts to create** (as the platform admin): one company, and in it one
`user` (applicant), one `reviewer_l1`, one `reviewer_l2`. For the isolation
tests, a second company with one `user`.

**Not yet verified by anyone:** Level C has never been run. The migrations
have not been applied to a real PostgreSQL. Please report what you find first
for these two.

---

## 1. Identity bundles: upload and extraction

Automated: `tests/test_identity_intake.py`

| # | Test | Expected |
| --- | --- | --- |
| 1.1 | `POST /cases` with `case_type` `identity_verification`, then `hiring_verification` | 201 for both |
| 1.2 | Upload a PDF, a JPG, a PNG and a TIFF to an identity case (files in `B12-image-formats/`) | 201 each; `content_type` matches the file |
| 1.3 | Upload a PNG to a `vendor_invoice` case | 415 `unsupported_file_type` (invoice cases stay PDF only) |
| 1.4 | Upload a PNG renamed to `.pdf` to an identity case | 415 `file_type_mismatch` |
| 1.5 | Upload a truncated image, an empty file, a file over the size limit | 422 `file_corrupted`, 400 `file_empty`, 413 `file_too_large` |
| 1.6 | Level C: after upload, poll `GET /cases/{id}` | Document goes pending → processing → complete; `extracted_fields.schema` is `identity`; `identity_fields` holds name, parent/spouse name, date of birth, gender, address, ID number, annual income, issuer, issue date |
| 1.7 | Level C: check `bounding_box` on the extracted fields | Present for values found on the page; highlights land on the right text |
| 1.8 | Level C: compare `identity_fields` with `ground_truth.json` for the same file | Same values. Differences here are extraction errors: note the file and field |
| 1.9 | Level C: upload the Hindi card (`B05-hindi-transliteration/01-national-id-card.png`) | `full_name.value` in Devanagari, `full_name.latin` "Ramesh Kumar Sharma" or close |
| 1.10 | An identity case does not run the forensic checks | Document `checks` is empty; case still reaches the review queue |

---

## 2. Contradiction detection

Automated: `tests/test_identity_comparison.py`

Without Azure: `python -m scripts.demo_identity_bundles <bundle>` shows the same
result the application should show.

| # | Bundle | Expected findings |
| --- | --- | --- |
| 2.1 | `B01-clean` | None |
| 2.2 | `B02-spelling-variants` | 4 harmless (spelling, address formatting); no conflict |
| 2.3 | `B03-initials-and-order` | 5 harmless (initials, title/word order) |
| 2.4 | `B04-name-abbreviation` | 5 harmless (Mohammad / Mohd. / Md) |
| 2.5 | `B05-hindi-transliteration` | 5 harmless (transliteration) |
| 2.6 | `B06-dob-minor-typo` | 1 conflict, medium (one day apart) |
| 2.7 | `B07-dob-year-conflict` | 1 conflict, high (1982 / 1997) |
| 2.8 | `B08-different-person` | 2 conflicts, critical (name and father's name) |
| 2.9 | `B09-similar-but-different-name` | 1 conflict, critical (Rahul / Rohit Verma) |
| 2.10 | `B10-income-conflict` | 1 conflict, critical (Rs. 60,000 / Rs. 4,80,000) |
| 2.11 | `B11-gender-and-address` | 2 conflicts: gender high, address medium |
| 2.12 | `B12-image-formats` | None |
| 2.13 | `H01-hiring-candidate` | 2 conflicts high (date of birth), 5 harmless (name) |
| 2.14 | `F01-child` | 1 conflict, critical (father's name Mahesh / Mukesh) |

Also check on `GET /cases/{id}` → `cross_document_findings[]`:

| # | Test | Expected |
| --- | --- | --- |
| 2.15 | Each finding has `classification`, `reason`, `severity`, `evidence` (two entries with `value`, `document_type`, `bounding_box`) and `regions` | Yes |
| 2.16 | Harmless findings | `severity` is always `info` |
| 2.17 | Re-upload a document or re-run the check | Findings are replaced, not duplicated |
| 2.18 | Try your own name pairs (unit level: `compare_names`) | Report any pair you think is judged wrongly. Known and intended: one-letter differences (Verma / Varma, Kiran / Karan) come out as medium "possible spelling error" |

---

## 3. Reviewing findings

Automated: `tests/test_finding_review_and_i18n.py`

`PATCH /cases/{id}/findings/{finding_id}` with `{"decision": "accepted" | "dismissed" | "pending", "note": "..."}`

| # | Test | Expected |
| --- | --- | --- |
| 3.1 | Reviewer accepts a conflict | `review_status` accepted, `resolution` `conflict_confirmed`, reviewer name and time set |
| 3.2 | Reviewer dismisses a conflict | `resolution` `no_issue` |
| 3.3 | Reviewer dismisses a harmless finding | `resolution` `conflict_confirmed` (the reviewer overrules the check) |
| 3.4 | Decision `pending` | Decision, note, reviewer and time cleared |
| 3.5 | `finding_counts` on the case and in the PATCH response | `open`, `conflict_confirmed`, `no_issue`, `ignored_as_harmless` add up after each decision |
| 3.6 | Applicant (`user`) tries the PATCH | 403 |
| 3.7 | Platform admin tries the PATCH | 403 |
| 3.8 | `reviewer_l1` on a case escalated to L2 | 403; `reviewer_l2` succeeds |
| 3.9 | PATCH after the case is approved or rejected | 409 |
| 3.10 | Finding id from another case; unknown ids | 404 |
| 3.11 | Audit history of the case | A `finding_reviewed` entry per decision with reviewer, role, previous decision and note |
| 3.12 | Decide a finding, then re-run the check | The decision is kept |

---

## 4. Messages and languages

Automated: `tests/test_finding_review_and_i18n.py`

| # | Test | Expected |
| --- | --- | --- |
| 4.1 | `GET /cases/{id}` | Each identity finding has `message` with `summary`, `explanation`, `action`, `field_label`, `severity_label` |
| 4.2 | `GET /cases/{id}?lang=hi` | Messages in Hindi; names, dates and addresses unchanged; works with no Google key |
| 4.3 | `?lang=zz` | Falls back to English, no error |
| 4.4 | `GET /i18n/languages` (no sign-in) | 13 languages. Without a Google key: `en` and `hi` available, the rest `available: false` |
| 4.5 | `GET /i18n/catalog?lang=hi` | Field, document, severity, reason and action labels in Hindi |
| 4.6 | `POST /i18n/translate` without a key | Strings come back in English, `complete: false` |
| 4.7 | With `GOOGLE_TRANSLATE_API_KEY` set: `?lang=ta`, `/i18n/translate` | Translated text; placeholders and people's details intact. **Never run against real Google: check the quality** |
| 4.8 | `POST /i18n/translate` with 301 strings, or a string over 500 characters | 422 |
| 4.9 | Read the Hindi messages as a Hindi speaker | Report anything unnatural or wrong (they are hand-written) |

---

## 5. Verified profile

Automated: `tests/test_profile_and_forms.py`

`GET /cases/{id}/profile`, `PUT /cases/{id}/profile/{field}` with `{"document_id": "..." | null}`

| # | Test | Expected |
| --- | --- | --- |
| 5.1 | Profile of `B01-clean` | All six details `agreed`, each with its source document; `ready: true` |
| 5.2 | Profile of `B03-initials-and-order` | Name is "Ajay Prakash Sharma" (the fullest form), status `agreed` |
| 5.3 | Profile of `B07-dob-year-conflict` | Date of birth `conflict`, no value, two candidates, no suggestion; `ready: false` |
| 5.4 | Profile of `H01-hiring-candidate` | Date of birth `conflict`; the 1998 group suggested; the degree certificate in `documents_to_correct` |
| 5.5 | Reviewer chooses a document for a disputed detail | Status `chosen`, value from that document, `ready` updates |
| 5.6 | `document_id: null` | Choice removed, back to `conflict` |
| 5.7 | Dismiss the conflict finding instead (section 3) | The detail becomes `agreed` |
| 5.8 | Choose a document that does not state the detail, or from another case | 422 |
| 5.9 | Applicant tries the PUT; PUT on a decided case; profile of an invoice case | 403; 409; 409 |
| 5.10 | Applicant opens the profile of their own case, then of someone else's | 200; 404 |

---

## 6. Form auto-fill

Automated: `tests/test_profile_and_forms.py`

`GET /forms`, `GET /cases/{id}/forms/{form_id}`

Forms: `income_certificate_application`, `scholarship_application`,
`domicile_certificate_application`, `employee_joining_form` (hiring cases only).

| # | Test | Expected |
| --- | --- | --- |
| 6.1 | `GET /forms`, then with `?case_type=hiring_verification` | Four forms; one form |
| 6.2 | Scholarship form for `B01-clean` | Name, parent, date of birth, age, gender, address, postal code, ID number, income `filled` with their source document; institution, course, bank account `to_fill` |
| 6.3 | Any form for `B07-dob-year-conflict` | Date of birth (and age) `needs_attention`, empty, with a note; `ready: false` |
| 6.4 | Settle that conflict (section 3 or 5), reload the form | Date of birth `filled` |
| 6.5 | Income certificate form for `B06-dob-minor-typo` | Annual income `to_fill` with "Not found on your documents" |
| 6.6 | `?lang=hi` | Labels, title and notes in Hindi; values unchanged |
| 6.7 | Employee joining form on an identity case; unknown form id | 404 |
| 6.8 | Age | Whole years as of today |

---

## 7. Family

Automated: `tests/test_family.py`

| # | Test | Expected |
| --- | --- | --- |
| 7.1 | `GET /family` before setting one up | `null` |
| 7.2 | `POST /family` | 201; the user is the head, listed as a member with relation `self` |
| 7.3 | `POST /family` again | 409 |
| 7.4 | `POST /family/members` (spouse, son, daughter, father, mother, other) | 201; blank name, relation `self` or an unknown relation → 422 |
| 7.5 | `PATCH` a member; `PATCH` the head's relation | 200; 409 |
| 7.6 | `DELETE` a member with no case; the head; a member who has a case | 200; 409; 409 |
| 7.7 | `POST /cases` with `family_member_id` as the head | 201; `GET /cases/{id}` shows `family_member` |
| 7.8 | Same call as another user, with an invoice case type, or with an unknown member id | 422 |
| 7.9 | Another applicant opens `GET /families/{id}`; a reviewer opens it | 404; 200 |
| 7.10 | Reviewer or other user tries to add or change a member | Not possible (404) |
| 7.11 | Platform admin on `/family` | 403 |
| 7.12 | Build family F01: head "Mahesh Chand Agrawal" (born 1975-02-08), spouse "Sarla Agrawal", daughter "Tanvi Agrawal"; submit bundles `F01-head`, `F01-spouse`, `F01-child` | Checks: identity `match` for all; address `match`; birth order `match`; daughter's parent name `not_checked` |
| 7.13 | Settle the daughter's father's-name conflict by choosing the marksheet | Parent name check becomes `conflict`, critical |
| 7.14 | Choose the identity card instead | Parent name check becomes `match` |
| 7.15 | Enter a member under a different name than their documents show | `member_identity` `conflict` |
| 7.16 | `?lang=hi` | Check labels and sentences in Hindi |

---

## 8. One site per organisation (subdomain)

Automated: `tests/test_subdomains.py`

Send the header `X-Org-Subdomain: <label>`, or set `APP_BASE_DOMAIN=localhost`
and use `http://<label>.localhost:...`.

| # | Test | Expected |
| --- | --- | --- |
| 8.1 | Platform admin creates a company without a subdomain | One is made from the name ("Tehsil Office, Indore" → `tehsil-office-indore`) |
| 8.2 | Create with `subdomain` `ab`, `admin`, `has space`; with one already used | 422; 409 |
| 8.3 | `PATCH /platform/companies/{id}` changes the subdomain; sends `""` | Changed; removed |
| 8.4 | `GET /organisation` with the header; with an unknown label; with no label | Organisation name; 404; nulls |
| 8.5 | A user signs in with their own organisation's label | 200, `company_subdomain` returned |
| 8.6 | The same user with another organisation's label | 401 "Incorrect email or password" (identical to a wrong password) |
| 8.7 | Platform admin with an organisation's label | 401; without a label 200 |
| 8.8 | Use organisation A's token with organisation B's label | 401 |
| 8.9 | Suspend a company, then `GET /organisation` and sign in | 404; 401 |
| 8.10 | No label anywhere | Everything works as before |

---

## 9. Isolation and permissions (regression)

Automated: `tests/test_multi_tenancy.py`, `tests/test_case_authorization.py`,
`tests/test_rls_postgres.py` (needs PostgreSQL; see the file header)

| # | Test | Expected |
| --- | --- | --- |
| 9.1 | A user of company B requests a case, finding, profile, form or family of company A | 404 every time |
| 9.2 | An applicant requests another applicant's case in the same company | 404 |
| 9.3 | Run `tests/test_rls_postgres.py` against a migrated PostgreSQL | Passes, including the new tables `families` and `family_members`. **Not yet run** |
| 9.4 | Invoice cases (the original product): upload, checks, risk score, approve/reject | Unchanged |

---

## 10. Frontend screens

Not covered by automated tests. Check each against sections 1–8.

| # | Screen | Check |
| --- | --- | --- |
| 10.1 | New bundle | Identity types selectable; images accepted; rejection messages shown |
| 10.2 | Case detail, identity layout | Person details per document; image and PDF viewers; highlights on click |
| 10.3 | Findings panel | Counts, grouping, severity chips, three-line message, harmless section |
| 10.4 | Side-by-side view | Both documents, both highlights, previous/next |
| 10.5 | Accept / dismiss | Buttons, note, undo, status line, hidden for applicants and on decided cases |
| 10.6 | Language switcher | Hindi changes messages and labels; unavailable languages are not offered |
| 10.7 | Verified profile | Four statuses, candidates, "use this", suggestion text |
| 10.8 | Forms | Three field states, source tags, print |
| 10.9 | My family | Set up, add/edit/remove, submit for a member, checks panel |
| 10.10 | Organisation sign-in | Name on the login page; "address not in use" page (Phase 7 frontend may not be built yet) |
| 10.11 | Invoice cases | Look and behave as before |

---

## Known issues and limits

- `tests/test_signature_task.py::test_signature_comparison_task_flow` fails
  without Azure storage settings. It failed before this work and is unrelated.
- Approving a case is not blocked while findings are open.
- Dates inside messages stay in English form ("12 March 1982") in every
  language.
- A filled form cannot be saved or exported.
- The exported case report (PDF) does not list identity findings.
- The case risk badge is not derived from identity findings.
- The Hindi bundle can only be regenerated on a machine with a Devanagari
  font.

## Reporting a problem

Give the section number, the bundle or file used, the request (or screen and
click), what you expected and what happened. For a wrong finding, include the
two values and the `reason` the API returned.
