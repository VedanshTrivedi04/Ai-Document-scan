# Upload Testing Guide: ID Cards and Supporting Documents

For a tester who will upload identity documents (an Aadhaar-style card, a PAN-style card, an income certificate, a voter card, an address proof) and check what the system reads and what it flags.

Companion to [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md), which covers the whole feature set. This guide goes deep on one thing: **uploading documents and checking the result.**

## Ground rules

1. **Fake data only.** Never upload a real person's Aadhaar, PAN or any real document. Use the files named below, or make your own with invented names (Part 8).
2. **The sample cards are generic.** The bundle files are called "national ID card" and "tax ID card" and carry the word SPECIMEN. They stand in for Aadhaar and PAN on purpose. Number formats are similar (masked 12-digit ID, 10-character tax ID).
3. **Expected results come from `sample-documents/identity-bundles/ground_truth.json`.** That file and the comparison rules have the same author. A match proves the system behaves as designed. It does not measure accuracy on real-world documents.
4. **Write down what you actually see.** Every table has an *Actual* column. Where this guide says *not defined*, nobody has decided the right answer yet. Record what happens and report it.

## 0. Before you start

### 0.1 What must be running

| Piece | Check |
| --- | --- |
| PostgreSQL, Redis | `docker compose ps` shows them up |
| API | `http://localhost:8000/docs` opens |
| Extraction worker | Celery worker on `extraction_queue` is running |
| Forensics worker | Celery worker on `forensics_queue,celery` is running (the cross-document check runs here) |
| Frontend | `http://localhost:5173` opens |
| Providers in `backend/.env` | OCR, LLM (and Vision LLM for images) set. Which provider is set is shown in `backend/.env`. Do not paste its keys into reports |
| Tesseract (only if `OCR_PROVIDER=local`) | Installed, with `eng` and `hin` language files; `TESSDATA_DIR` set |

Startup commands are in [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) section 0.

### 0.2 Quick pre-check without the app (optional, recommended)

This reads the documents with the configured providers and compares the result with `ground_truth.json`. No database or queue needed. It needs `OCR_PROVIDER=local`.

```bash
cd backend
./.venv/Scripts/python -m scripts.check_pipeline_on_bundles --ocr-only      # only show the text read
./.venv/Scripts/python -m scripts.check_pipeline_on_bundles B07 B05          # chosen bundles, with the LLM
```

If a field is already wrong here, it will be wrong in the app. Note the file and field, and stop testing that bundle until it is understood.

### 0.3 Accounts

| Account | Used for |
| --- | --- |
| A citizen account (create it on the Sign Up tab at `http://localhost:5173`) | Uploads, own profile, family |
| A reviewer (`reviewer_l1`) on a company | Accept / Dismiss on findings, case approval |

### 0.4 Where the files are

`sample-documents/identity-bundles/`. One folder per bundle (`B01-clean`, `B02-spelling-variants` and so on). Two zips are also there for the bulk upload tests.

---

## 1. The upload screen

Open **New upload** (route `/cases/new`).

| # | Check | Expected | Actual |
| --- | --- | --- | --- |
| 1.1 | Question "What are you submitting?" | Two choices: *Person's documents* and *Claim documents* | |
| 1.2 | Choose *Person's documents* | A "Specific case type" list appears with the identity case types | |
| 1.3 | Choose *Claim documents* | Invoice style case types appear; this guide does not test those | |
| 1.4 | Signed in as a family head with members | A "Link to household member" list appears | |
| 1.5 | Person with an earlier identity case | A banner says the new upload will join the active profile (case number shown) and offers *Create separate bundle instead* | |
| 1.6 | Submit with no file | Blocked with a clear message; no case created | |

## 2. One document at a time

Create a new case for each row (or use *Add document to profile* inside a case). Use the files from `B01-clean` unless noted.

| # | Upload | What to check on the case page | Expected | Actual |
| --- | --- | --- | --- | --- |
| 2.1 | `01-national-id-card.pdf` | Status moves pending, processing, complete | Document type: national ID card. Fields: Kavita Rao Deshmukh; parent Suresh Rao Deshmukh; DOB 12 March 1990; female; 22 Tilak Path, Sector 4, Indore, Madhya Pradesh 452001; ID XXXX XXXX 1107 | |
| 2.2 | `02-tax-id-card.pdf` | Same | Document type: tax ID card. Name, parent, DOB as above; ID QWKPD4417L. Gender and address empty (the card has none) | |
| 2.3 | `03-income-certificate.pdf` | Same | Income 120,000 per year; issue date 10 January 2026; ID IC/2026/004417; address as above; DOB empty | |
| 2.4 | `B02-.../03-address-proof.pdf` | Same | Document type: address proof; ID EB-7741-2290; issue date 3 February 2026; address "45 M.G. Rd, Nr Bus Stand, Ujjain, MP - 456001" | |
| 2.5 | `B04-.../03-income-certificate.pdf` | Same | Name "Md Asif Khan"; income 96,000 | |
| 2.6 | `B03-.../03-voter-id-card.pdf` | Same | Name "Shri Sharma Ajay Prakash"; ID SVX4410927 | |
| 2.7 | `H01-hiring-candidate/02-marksheet.pdf` | Same | Document type: marksheet; name "Nikhil M. Joshi"; issue date 30 May 2014 | |

For each: after the status says complete, open the **person details** for the document and compare every field with the Expected column. A field that is wrong, missing, or shown with low confidence goes into the report with file name and field.

**Also check, for every upload**

- [ ] The right document type is shown.
- [ ] Clicking a value highlights it on the document (page and box in the right place).
- [ ] Empty fields are shown as empty, not as made-up values.
- [ ] No forensic checks, risk score or invoice wording appear on an identity case.

## 3. A full bundle: the main test

Upload all documents of one bundle into one case, then wait for the findings. Run these in order. The expected findings come straight from `ground_truth.json`; "info" means a harmless difference that is shown but ignored.

### 3.1 No finding expected

| Bundle | Documents | Expected |
| --- | --- | --- |
| B01-clean | national ID, tax ID, income certificate | **No findings.** Case shows no conflict |
| B12-image-formats | `01-...jpg`, `02-...png`, `03-address-proof.tiff` | **No findings.** All three image formats read correctly |

### 3.2 Harmless differences: must be shown as ignored, never as conflicts

| Bundle | Differences in the documents | Expected findings (all harmless, severity info) |
| --- | --- | --- |
| B02-spelling-variants | Sunita Choudhary / Suneeta Chowdhary; "45 Mahatma Gandhi Road" / "45 M.G. Rd" | full_name: spelling_variant (ID vs tax card); parent name: spelling_variant; full_name: spelling_variant (tax card vs address proof); address: address_formatting |
| B03-initials-and-order | Ajay Prakash Sharma / A. P. Sharma / Shri Sharma Ajay Prakash | name: initials; parent name: initials; name: honorific_or_word_order (ID vs voter); name: initials (tax vs voter); parent name: initials (tax vs voter) |
| B04-name-abbreviation | Mohammad / Mohd. / Md | name and parent name: abbreviation, across the three document pairs (5 findings) |
| B05-hindi-transliteration | Hindi ID card against English cards | name: transliteration (ID vs tax; ID vs income); parent name: transliteration (both pairs); address: transliteration (ID vs income) |

### 3.3 Real conflicts: must be flagged with the right severity

| Bundle | Difference | Expected finding | Severity |
| --- | --- | --- | --- |
| B06-dob-minor-typo | DOB 15/08/1995 against 16/08/1995 | date_of_birth: date_minor_difference | medium |
| B07-dob-year-conflict | DOB 12/03/1982 against 12/03/1997 (ID vs voter card) | date_of_birth: date_year_difference | high |
| B08-different-person | Rahul Verma against Sanjay Singh, parent Dinesh Verma against Harpal Singh | full_name: different_name; parent name: different_name | critical |
| B09-similar-but-different-name | Rahul Verma against Rohit Verma | full_name: different_name. Similar spelling must **still** be a conflict | critical |
| B10-income-conflict | Income 60,000 against 480,000 (two income certificates) | annual_income: income_difference | critical |
| B11-gender-and-address | Gender female against male; Khargone 451001 against Khandwa 450001 | gender: gender_difference (high); address: address_locality_difference (medium) | high, medium |

### 3.4 Mixed bundles

| Bundle | Case type | Expected |
| --- | --- | --- |
| H01-hiring-candidate | `hiring_verification` | Harmless: name with extra middle name or initial (5 findings: ID vs marksheet, ID vs degree, marksheet vs degree, marksheet vs experience letter, degree vs experience letter). **Conflict (high):** date of birth 17 May 1998 (ID, marksheet) against 17 May 1999 (degree certificate). Two findings: ID vs degree, marksheet vs degree |

### 3.5 What to verify on every bundle

- [ ] The count of findings equals the table (open the findings panel and count; harmless ones live in their own section).
- [ ] Each finding names the two documents, shows both values side by side, and highlights both on the pages.
- [ ] Each message has three parts: what differs, why, what to do. Wording is plain, not technical.
- [ ] The harmless/conflict label matches the table. **A conflict shown as harmless is a serious bug; report it first.**
- [ ] Severity chip matches the table.
- [ ] The case does not appear "clean" while a conflict exists.

Record the result for each bundle:

| Bundle | Findings expected | Findings seen | Missing | Extra | Pass? |
| --- | --- | --- | --- | --- | --- |
| B01 | 0 | | | | |
| B02 | 4 | | | | |
| B03 | 5 | | | | |
| B04 | 5 | | | | |
| B05 | 5 | | | | |
| B06 | 1 | | | | |
| B07 | 1 | | | | |
| B08 | 2 | | | | |
| B09 | 1 | | | | |
| B10 | 1 | | | | |
| B11 | 2 | | | | |
| B12 | 0 | | | | |
| H01 | 7 | | | | |

(Counts are the number of entries under `expected_findings` for each bundle in `ground_truth.json`.)

## 4. Adding documents one by one (profile building)

This is how a real citizen will use it: upload one card today, another later.

| # | Steps | Expected | Actual |
| --- | --- | --- | --- |
| 4.1 | New upload of `B06-.../01-national-id-card.pdf` | Case created. Only one document, so **no cross-document findings** | |
| 4.2 | Open the case, click **Add document to profile**, upload `B06-.../02-tax-id-card.pdf` | Document joins the same case (no second case). When processing ends, the DOB conflict (medium) appears | |
| 4.3 | Go to **New upload** again, choose the same person, upload a third file | The banner offers to join the active profile and the file lands in the same case | |
| 4.4 | Same, but click **Create separate bundle instead** | A new, separate case is created; findings are not mixed with the first | |
| 4.5 | Add a document that fixes nothing (an identical copy of the first) | A duplicate is accepted or flagged. *Not defined*: record what happens | |
| 4.6 | Refresh the page while a document is processing | Status resumes; nothing is lost | |

## 5. Reviewing findings

Sign in as `reviewer_l1` (or, for a citizen's own case, the family head), open a case with findings (use B07 or B08).

| # | Steps | Expected | Actual |
| --- | --- | --- | --- |
| 5.1 | Open one conflict and click **Accept** | Status line says the conflict is confirmed; counts update | |
| 5.2 | Open another and click **Dismiss**, with a note | Status shows no issue; the note is kept | |
| 5.3 | Click **undo** (set back to pending) | Finding returns to open | |
| 5.4 | Dismiss a *harmless* finding | It is treated as a real conflict (a reviewer disagreeing with the system) | |
| 5.5 | Re-run the check (add another document to the case) | Earlier decisions are kept | |
| 5.6 | Open the same case as a plain `user` | No Accept / Dismiss buttons | |
| 5.7 | Approve the case, then try to change a finding | Refused; the case is decided | |
| 5.8 | Open **Audit history** | `finding_reviewed` and the case decision events are listed with actor and time | |

## 6. Verified profile and forms (after upload)

| # | Steps | Expected | Actual |
| --- | --- | --- | --- |
| 6.1 | Open a conflict case (B07). View the verified profile | Date of birth shows status *conflict* with both candidates | |
| 6.2 | Click **Use this** on one value | Status becomes *chosen*; profile can reach *ready* once no conflict is left | |
| 6.3 | Open a clean case (B01) profile | Details show *agreed*; the missing items show *missing* (for example nothing for a detail no card carries) | |
| 6.4 | Open **Forms**, then *income certificate application* | Fields from verified documents are filled and marked; the rest are left to fill; age derived from DOB | |
| 6.5 | Switch language to Hindi | Messages and form labels change to Hindi. Names and values on the documents are **not** translated | |

## 7. Wrong, strange or hostile uploads

None of these should crash the page or create a broken case.

| # | Upload | Expected | Actual |
| --- | --- | --- | --- |
| 7.1 | A `.txt` or `.docx` file | Rejected with a clear message (unsupported file type) | |
| 7.2 | A PNG renamed to `.pdf` | Rejected (file type does not match its content) | |
| 7.3 | An empty file (0 bytes) | Rejected (file empty) | |
| 7.4 | A truncated image (cut a JPG in half with a hex editor or by copying only part of it) | Rejected (file corrupted) | |
| 7.5 | A very large file | Rejected (file too large) with the limit shown. The limit is set per company; check *Settings* for the value | |
| 7.6 | A password-protected PDF | *Not defined*. Record the message | |
| 7.7 | A blank page PDF | Document completes with no fields or fails with a readable message. Never made-up values | |
| 7.8 | A photo of a document taken at an angle, or a screenshot of a phone | *Not defined*. Record which fields were read | |
| 7.9 | The same file uploaded twice in a row (double click on Submit) | One case, one document, not two | |
| 7.10 | A document in an unsupported language (for example Tamil) | *Not defined*. Record what is read | |
| 7.11 | Stop the extraction worker, upload, then restart it | Document stays *pending*, then completes after restart (a stuck-document job also exists) | |

## 8. Your own test cards (the Aadhaar and PAN images)

`scratch/aadhaar_card.png` and `scratch/pan_card.png` are two invented cards for one person. They were not generated by the bundle script and are not in `ground_truth.json`, so there is no verified expectation. Read from the images:

| | Aadhaar-style card | PAN-style card |
| --- | --- | --- |
| Name | Rahul Sharma | Rahul K. Sharma |
| DOB | 15/08/1990 | 15/08/1991 |
| ID | 9876 5432 1098 | ABCPS1234F |
| Address | 124 MG Road, New Delhi, 110001 | 124 MG Road, New Delhi, 110001 |

Upload both into one case.

| # | Check | Predicted by the rules | Actual |
| --- | --- | --- | --- |
| 8.1 | Fields read from each image match the table above | All four per card | |
| 8.2 | Date of birth finding | Conflict. The rules treat a different year as high severity, even when only one year apart | |
| 8.3 | Name finding | Not predicted with confidence. The "K." is an extra initial; the likely outcomes are *harmless* (extra middle name or initial) or *partial name* (low). Record which one | |
| 8.4 | Address finding | None (identical) | |
| 8.5 | ID numbers | Not compared: they are different kinds of card | |

**Ready-made test cards.** `sample-documents/test-cards/` holds 14 sets (31 files) of Aadhaar-style and PAN-style cards, written by `backend/scripts/generate_test_cards.py` (re-run it with `python -m scripts.generate_test_cards`). `MANIFEST.json` there lists, per set, what the cards state and what the detector should say. Upload each set into its own case.

| Set | What it tests | Expected |
| --- | --- | --- |
| T01-clean | All details agree | No findings |
| T02-initial-and-year | "Rahul K. Sharma" against "Rahul Sharma"; birth year 1990 against 1991 | DOB conflict (high); name not predicted, record it |
| T03-dob-day-month-swapped | 12/03 against 03/12 | DOB conflict (low) |
| T04-dob-one-digit | 15/08 against 16/08 | DOB conflict (medium) |
| T05-dob-15-years | 1982 against 1997 | DOB conflict (high) |
| T06-honorific-capitals | SHRI SURESH KUMAR GUPTA against Suresh Kumar Gupta | Harmless |
| T07-spelling-variant | Sunita Choudhary against Suneeta Chowdhary | Harmless (spelling_variant) |
| T08-different-person | Rahul Verma against Sanjay Singh | Critical conflict |
| T09-similar-name | Rahul Verma against Rohit Verma | Critical conflict, never harmless |
| T10-gender-mismatch | Two ID cards, female against male | Conflict (high) |
| T11-income-gap | Rs. 60,000 against Rs. 4,80,000 | Critical conflict |
| T12-masked-id-address-format | Masked ID; "Colony, MP" against "Clny, Madhya Pradesh" | No conflict; address harmless |
| T13-hindi-vs-english | Hindi card against English card | Harmless (transliteration) |
| T14-scan-quality | One card: clean, rotated 5°, blurred, low resolution, heavy JPEG | Not defined; upload each alone, record which fields were read |

These expectations are the author's reading of the comparison rules. They are not in `ground_truth.json`, so the `check_pipeline_on_bundles` script does not cover them.

**Making more cards.** Draw cards with invented names (an image editor, or the same Python approach as `backend/scripts/generate_identity_bundles.py`). Keep SPECIMEN on them. Useful variations, one change at a time so you know what caused a result:

| Change | Why |
| --- | --- |
| Swap DD and MM in the DOB (12/03 against 03/12) | Day and month swapped should be a low conflict |
| Remove the postal code on one card | Address compared without a code |
| Income in lakh notation (4,80,000) against plain (480000) | Both must read as the same number |
| Name in all capitals against mixed case | Must match exactly |
| Add a title (Shri, Smt, Dr) | Honorific must be ignored |
| Daughter of / son of / wife of on different cards | Parent or spouse name still compared |
| Mask the ID number (XXXX XXXX 1098) against a full one | Masked positions agree with anything |
| Two cards with different ID numbers of the same kind | Conflict (high) |

## 9. Hindi and image documents

| # | Steps | Expected | Actual |
| --- | --- | --- | --- |
| 9.1 | Upload `B05-.../01-national-id-card.png` alone | Name in Devanagari (रमेश कुमार शर्मा) with a Latin form "Ramesh Kumar Sharma" or close; DOB 14 September 1979; ID XXXX XXXX 5512 | |
| 9.2 | Upload the full B05 bundle | Five transliteration findings, all harmless; none as a conflict | |
| 9.3 | Upload B12 (JPG, PNG, TIFF) | All three read; no findings | |
| 9.4 | Compare image and PDF of the same person | Same values read from each | |

B05 is the most fragile bundle (Hindi on an image). If it fails here, run the pre-check in 0.2 with `B05` to see whether the problem is the text reading or the later steps.

## 10. Family uploads

Uses bundle F01 (head, spouse, child). Sign in as a citizen, open **My family**, set up the household.

| # | Steps | Expected | Actual |
| --- | --- | --- | --- |
| 10.1 | Add three members: head Mahesh Chand Agrawal, spouse Sarla Agrawal, child Tanvi Agrawal (enter the details as printed on the cards) | Members listed | |
| 10.2 | Upload `F01-head` files for the head, `F01-spouse` for the spouse, `F01-child` for the child, choosing the member in "Link to household member" | Each member gets a case with the member's name | |
| 10.3 | Head and spouse cases | No findings | |
| 10.4 | Child case | One finding, critical: father's name "Mahesh Chand Agrawal" (ID) against "Mukesh Chand Agrawal" (marksheet) | |
| 10.5 | Family checks panel | Member identity, shared address and parent name checks. A check that cannot be done shows *not checked* rather than guessing | |
| 10.6 | Settle the child's finding (Use this, with the correct father) | Parent-name check changes after the member's own documents are settled | |
| 10.7 | Sign in as a different citizen and try the family's case URL | Not found or not allowed. No data of the first family is visible | |

## 11. Bulk upload

| # | Steps | Expected | Actual |
| --- | --- | --- | --- |
| 11.1 | `identity-verification-bundles.zip` through **Bulk upload** | One case per folder; processed like single uploads | |
| 11.2 | `hiring-verification-bundles.zip` | One hiring case, same result as 3.4 | |
| 11.3 | Compare the results with section 3 | Same findings as when uploaded by hand | |

## 12. What to hand back

Create a short report with these, even if everything passed.

1. The bundle table from 3.5 filled in.
2. Every row with a different *Actual*, with: section and row number, file name, the field, what you expected, what you saw (screenshot of the case page), and the `reason` shown for a finding.
3. The *not defined* rows (4.5, 7.6, 7.7, 7.8, 7.10, 8.3), with what happened.
4. The pre-check output from 0.2 if you ran it.
5. Anything confusing in the wording of messages.

**Severity of problems, for sorting:**

| Level | Example |
| --- | --- |
| Blocker | A real conflict shown as harmless or not shown (B07, B08, B09, B10 missing a finding) |
| Major | A harmless variant shown as a conflict (B02 to B05), a wrong field read, upload that crashes |
| Minor | Wording, layout, wrong label colour |

## Known limits (so you do not report them as new)

- Nothing in this guide has been run end to end by the author of the guide. Treat every *Expected* as the intended behaviour, not as proof that it works.
- Approving a case is not blocked while findings are open.
- Dates inside messages stay in English form in every language.
- A filled form cannot be saved or exported.
- The exported case report (PDF) does not list identity findings.
- The case risk badge is not derived from identity findings.
- Extraction quality on real photographs and low-quality scans is unknown.
