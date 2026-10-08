# Demo Script — Document Contradiction Detector

For the person presenting. Two parts:

- **Part A (3 minutes, always works):** the detector in a terminal. Needs only
  Python. Use it if cloud keys are missing or the network fails.
- **Part B (7 minutes):** the full application in the browser. Needs Docker,
  Azure keys and the frontend.

Rehearse Part B once end to end before presenting. It has not been run against
the cloud services yet; see "Before the day".

---

## Before the day

1. **Part A check.** From `backend/`:

   ```bash
   python -m venv .venv
   ./.venv/Scripts/activate          # Windows;  source .venv/bin/activate elsewhere
   pip install -r requirements.txt
   python -m scripts.demo_identity_bundles
   ```

   The last line must read `16 bundles, 42 documents: 11 conflicts flagged, 24
   harmless differences ignored.` and every row `as expected`.

2. **Part B setup.**

   ```bash
   docker compose up -d                       # Postgres, Redis, PgBouncer
   cd backend
   cp .env.example .env                       # then fill in the keys below
   alembic upgrade head
   python seed.py                             # platform admin: admin@example.com / ChangeMe123!
   uvicorn app.main:app --reload
   ```

   Keys to fill in `backend/.env`:

   | Setting | Needed for |
   | --- | --- |
   | `AZURE_STORAGE_CONNECTION_STRING` | storing uploads (nothing works without it) |
   | `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`, `_KEY` | OCR |
   | `AZURE_OPENAI_KEY`, `_ENDPOINT`, `_DEPLOYMENT_NAME` | extraction |
   | `GOOGLE_TRANSLATE_API_KEY` | optional; languages other than English and Hindi |
   | `APP_BASE_DOMAIN=localhost` | optional; one site per organisation |

   Two workers, each in its own terminal (Windows needs `--pool=threads`):

   ```bash
   celery -A app.tasks.celery_app worker -Q extraction_queue -n extraction@%h --pool=threads -c 4 --loglevel=info
   celery -A app.tasks.celery_app worker -Q forensics_queue,celery -n forensics@%h --pool=threads -c 4 --loglevel=info
   ```

   Frontend:

   ```bash
   cd frontend
   npm install
   npm run dev                                # http://localhost:5173
   ```

3. **Accounts.** Sign in as the platform admin, then:
   - Platform › Companies: create "Tehsil Office, Indore".
   - Platform › Users: create one **User** (the applicant) and one
     **Reviewer L1** in that company.

4. **Pre-process the bundles.** As the applicant, create one identity
   verification case per bundle listed in Part B and upload its files from
   `sample-documents/identity-bundles/<bundle>/`. Wait until every case shows
   its findings. Do this before presenting: reading a document through the
   cloud services takes time, and a live upload should be shown once, not
   waited on five times.

5. **Check what the real services returned.** For each pre-processed case,
   compare the findings on screen with the terminal output for the same bundle
   (`python -m scripts.demo_identity_bundles B07`). If they differ, the
   extraction read something differently from the ground truth. Note which
   bundles match and present those.

---

## Part A — the detector in a terminal (3 minutes)

| Step | Type | Say |
| --- | --- | --- |
| 1 | `python -m scripts.demo_identity_bundles` | "Sixteen bundles of made-up documents, forty-two files. Eleven real conflicts flagged, twenty-four harmless differences ignored. Every bundle matches what we expected." |
| 2 | `python -m scripts.demo_identity_bundles B04` | "Mohammad, Mohd. and Md on three documents. Five differences, all ignored, each with its reason." |
| 3 | `python -m scripts.demo_identity_bundles B09` | "Rahul Verma and Rohit Verma. They look alike, and a similarity score would pass them. We flag it as critical, because no naming convention explains the difference." |
| 4 | `python -m scripts.demo_identity_bundles B07 --lang hi` | "A birth year fifteen years apart, explained in Hindi: what differs, why it matters, what to do." |
| 5 | `python -m scripts.demo_identity_bundles H01 --form employee_joining_form` | "A job candidate. Two documents say 1998, the degree says 1999, so the degree is named as the one to correct. The joining form fills itself and leaves the date of birth empty until that is settled." |
| 6 | `python -m scripts.demo_identity_bundles F01` | "A family of three. The child's marksheet names a different father, so the family check waits until a reviewer settles it." |

Say once, clearly: "This terminal run starts from the correct reading of each
document. Reading the files themselves is done by the cloud OCR in the full
application."

---

## Part B — the full application (7 minutes)

Open the cases you pre-processed. Suggested order:

| Minute | Screen | Do | Say |
| --- | --- | --- | --- |
| 0:00 | New bundle | As the applicant, start a new identity verification case and drop in the three files of `B12-image-formats` (JPG, PNG, TIFF). Leave it processing. | "Scans and photos are accepted, not only PDFs. Each file is checked before it is stored." |
| 0:45 | Case `B01-clean` | Open it. | "Three documents that agree. Nothing is flagged. The only difference was the date format, and that is not a difference." |
| 1:15 | Case `B03-initials-and-order` | Open the "ignored as harmless" section. | "A. P. Sharma, Ajay Prakash Sharma, Shri Sharma Ajay Prakash. One person. We show what we ignored and why, so nothing is hidden." |
| 2:00 | Case `B05-hindi-transliteration` | Show the Hindi identity card beside the English ones. | "A Hindi card against English documents: the names are matched through their Latin reading." |
| 2:45 | Case `B07-dob-year-conflict` | Sign in as the reviewer. Open the finding, then "Show on documents". | "The two values, highlighted where they are printed, side by side." |
| 3:30 | Same case | Click **Confirm conflict**, add a note. Show the audit history. | "The reviewer decides each finding. Who decided, when, and why is recorded and cannot be edited." |
| 4:15 | Same case | Switch the language to Hindi. | "The same finding in Hindi. Only our own sentence templates are translated; the person's details never leave the server." |
| 4:45 | Case `B09-similar-but-different-name` | Show the critical finding. | "Rahul and Rohit Verma. Similar spelling, different person, critical." |
| 5:15 | Case `H01-hiring-candidate` | Show the verified profile, then open the employee joining form. | "The same engine for hiring. The profile names the document to correct, and the form is filled from what the documents agree on." |
| 6:15 | My family | As the applicant, show the family with its members and the family checks. | "One person manages the whole household's documents. The checks run across members: same address, parent's name, dates of birth in order." |
| 6:45 | Case from minute 0:00 | Return to the bundle uploaded at the start. | "And the bundle we uploaded at the beginning has been read: three image files, all agreeing." |

If the organisation subdomain is set up, start at
`http://tehsil-office-indore.localhost:5173` and point out the organisation's
name on the sign-in page.

---

## If something fails

| Problem | Do |
| --- | --- |
| A document stays "pending" | The extraction worker is not running or the Azure keys are wrong. Continue with the pre-processed cases. |
| A case shows no findings where some are expected | Compare with the terminal output for that bundle and say that the live reading differed; show the terminal result. |
| Sign-in fails on a subdomain | Use plain `http://localhost:5173`. |
| The browser or network fails entirely | Run Part A. |

---

## Questions to expect

| Question | Answer |
| --- | --- |
| How accurate is it? | "On our sixteen synthetic bundles every finding matches the expected result. We wrote both the documents and the expected results, so that is a consistency check, not an independent benchmark. We also test more than forty name and address cases outside the bundles." |
| Why rules and not a model for the comparison? | "So the same bundle always gives the same answer and every finding has a reason a clerk can read. The model is used where it is strong: reading the document." |
| What about names a rule cannot judge? | "One-letter differences such as Kiran and Karan are flagged as medium for a person to decide. We do not guess." |
| Does it use real identity documents? | "No. Every document is generated by our script, marked as a specimen, with invented people." |
| Which languages? | "Hindi documents are read and compared. Messages are in English and Hindi out of the box, and eleven more Indian languages through Google Translation." |
| Is personal data sent for translation? | "No. Only our sentence templates are translated; values are filled in on our server." |
| What is not finished? | "Handwritten documents are not reliably read; approval is not yet blocked while findings are open; a filled form cannot yet be saved or exported." |
