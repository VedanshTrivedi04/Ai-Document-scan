# Frontend Prompts, Phase by Phase

The exact briefs given to the frontend agent after each backend phase. Kept so
another agent can see what the frontend was asked to build and against which
API contract. Phase 2 and Phase 8 had no frontend work.

Companion to [../MEMORY.md](../MEMORY.md). The same API contracts, kept up to
date, are in [DEVELOPMENT_PHASES.md](DEVELOPMENT_PHASES.md).

Whether each brief was fully carried out has not been verified by the backend
author. See "Frontend state" in MEMORY.md.

---

## Phase 1 — Intake and extraction

```
You are working in the frontend/ folder (React + TypeScript + Vite, Tailwind, shadcn/ui,
TanStack Query). The backend now supports "identity bundles": one person's documents
(identity card, address proof, income certificate, ...) uploaded together. Update the
frontend for Phase 1. Do not change any backend file. Existing invoice case types must
keep working exactly as they do now.

BACKEND CONTRACT (already live)

1. Two new case types for POST /cases and the case_type filter:
   "identity_verification" and "hiring_verification".

2. POST /cases/{id}/documents on a case of either type accepts PDF, JPEG, PNG and TIFF.
   All other case types still accept PDF only. Rejections keep the same shape:
   detail: { code, message }. Codes: file_empty, file_too_large, unsupported_file_type,
   file_type_mismatch, file_corrupted, file_password_protected.

3. GET /cases/{id}: for these cases each document's extracted_fields is
   {
     "schema": "identity",
     "document_type_confidence": number,
     "identity_fields": {
       "full_name":             { value, latin, confidence, uncertain, bounding_box? },
       "parent_or_spouse_name": { value, latin, confidence, uncertain, bounding_box? },
       "date_of_birth":         { value (YYYY-MM-DD), raw_text, confidence, uncertain, bounding_box? },
       "gender":                { value ("male"|"female"|"other"|null), raw_text, confidence, uncertain },
       "address":               { value, latin, postal_code, confidence, uncertain, bounding_box? },
       "id_number":             { value, confidence, uncertain, bounding_box? },
       "annual_income":         { value (number|null), currency, raw_text, confidence, uncertain, bounding_box? },
       "issuing_authority":     { value, confidence, uncertain, bounding_box? },
       "issue_date":            { value (YYYY-MM-DD), raw_text, confidence, uncertain, bounding_box? }
     },
     "core_fields": { ...same keys as before, every value null... },
     "additional_fields": [ { field_name, value, confidence, uncertain } ]
   }
   bounding_box = { page, x, y, width, height }, all fractions 0-1 of the page; it is absent
   when the value could not be found on the page. Any value can be null.

4. document_type for these documents is one of: national_id_card, tax_id_card,
   voter_id_card, driving_licence, passport, birth_certificate, income_certificate,
   address_proof, caste_certificate, domicile_certificate, marksheet, degree_certificate,
   experience_letter, payslip, other.

5. These cases have no forensic checks: a document's `checks` array is empty. Cross-document
   findings arrive in a later phase; for now the list is empty.

WHAT TO BUILD

A. Types (src/types/case.ts)
   - Add both case types to CASE_TYPES and CASE_TYPE_LABELS ("Identity verification",
     "Hiring verification").
   - Add the 15 document types to DOCUMENT_TYPE_LABELS with readable names
     ("Identity card", "Tax identity card", "Income certificate", ...).
   - Add IdentityFields types and make ExtractedFields a union discriminated by
     schema === "identity". Add a helper isIdentityCase(caseType).
   - getDocumentRole: return "other" for the identity document types (claim/evidence does
     not apply).

B. Upload (src/lib/uploadLimits.ts, src/components/upload/FileDropzone.tsx,
   src/pages/NewCasePage.tsx, src/pages/BulkUploadPage.tsx)
   - FileDropzone takes the accepted types as a prop. For identity case types accept
     .pdf,.jpg,.jpeg,.png,.tif,.tiff; otherwise PDF only as today.
   - The dropzone hint text follows the case type: "PDF, JPG, PNG or TIFF" vs "PDF only".
   - Show the backend's `message` for a rejected file as it is.
   - NewCasePage has an isPdf check for previews: show an <img> thumbnail for image files.

C. Case detail (src/pages/CaseDetailPage.tsx, src/components/case/PdfOverlayViewer.tsx)
   - When extracted_fields.schema === "identity", render a "Person details" panel
     instead of the invoice fields panel (issuer / reference / subtotal / tax / total).
     The current code reads core_fields.issuer.value directly; do not show that panel
     for identity documents.
   - Hide the forensic checks panel and the risk-score block for identity cases; they
     are always empty there.
   - Image documents: the viewer must show the image (one page) with the same overlay
     layer the PDF viewer uses. Bounding boxes are fractions of the page, so the same
     overlay maths works on an <img>.
   - Clicking a field row highlights its bounding_box on the document and scrolls to it.
     A field without bounding_box has no highlight; show a small "not located" hint.

D. Lists (CaseQueuePage, MyCasesPage)
   - The new case types show their labels and are available in the case-type filter.

UI IDEA

New bundle page
   - First choice is "What are you submitting?" as two large cards instead of a
     dropdown item: "Person's documents" (identity / hiring) and "Claim documents"
     (the existing types). Picking the first reveals a short checklist of typical
     documents: identity card, address proof, income certificate.
   - Each uploaded file is a card with a thumbnail, file name, size and status chip.

Case detail page, identity layout: two columns
   - Left (about 60%): document tabs across the top, each tab labelled with the document
     type ("Identity card", "Income certificate") rather than the file name, with the
     file name as a tooltip. Below it the document viewer with highlights.
   - Right (about 40%): "Person details" card. One row per field in this order:
     Name, Parent / spouse name, Date of birth, Gender, Address, ID number,
     Annual income, Issued by, Issue date.
     Each row: label, value, and under it in smaller muted text the Latin form when it
     differs from the value. Dates shown as "12 April 1991". Income as "INR 1,20,000".
     A field with uncertain: true gets a small amber "Please check" chip.
     A null value shows "Not on this document" in muted text, never an empty cell.
   - Text in Devanagari or another non-Latin script must render correctly; use a font
     stack that covers it (for example "Noto Sans", "Noto Sans Devanagari", system-ui).
   - While a document is pending or processing, show a skeleton for the panel and the
     existing status chip; keep the existing polling.

Wording
   - Plain words throughout. "Person details", not "Extracted identity fields".
     "Please check", not "Low confidence". No raw field keys such as
     parent_or_spouse_name on screen.

DONE WHEN
   - Creating an identity verification case, uploading one PNG and one PDF, and opening
     the case shows both documents, the Person details panel and working highlights.
   - A vendor invoice case behaves exactly as before, including refusing images.
   - npm run build and the linter pass.
   - Tell me what you could not verify (the backend needs Azure keys to process
     documents, so test the panel with mocked case data if processing is unavailable).
```

---

## Phase 2 — Synthetic bundles (no frontend work)

```
No frontend work in Phase 2. One thing you can use: sample-documents/identity-bundles/
now holds synthetic test bundles. ground_truth.json there gives, for every document,
the exact `identity_fields` object the backend returns (Phase 1 shape), so you can
build mock case data from it to test the Person details panel without the backend
processing anything. The files themselves (PDF, JPG, PNG, TIFF) are valid uploads for
an identity_verification case. All of it is invented data.
```

---

## Phase 3 — Findings

```
Phase 3, frontend/ only. The backend now finds contradictions between the documents of
an identity bundle. Show them. Do not change backend files. Invoice cases must keep
working as they do now.

BACKEND CONTRACT (live)

GET /cases/{id} -> cross_document_findings[]. For identity cases
(case_type identity_verification or hiring_verification) each item is:

{
  id, created_at,
  field_name: "full_name" | "parent_or_spouse_name" | "date_of_birth" | "gender" |
              "address" | "annual_income" | "id_number",
  finding_type: "identity_consistency",
  classification: "harmless_variant" | "conflict",
  reason: string,            // machine key, e.g. "initials", "date_year_difference"
  severity: "info" | "low" | "medium" | "high" | "critical",   // "critical" is new
  description: string,       // one plain sentence, ready to show as it is
  document_ids: [docA, docB],
  evidence: [                // always two entries, same order as document_ids
    { document_id, document_type, document_filename, value, bounding_box | null },
    { ... }
  ],
  regions: [ { document_id, document_filename, field, label, value, caption, other,
               bounding_box } ]   // same shape the invoice findings already use
}

- harmless_variant always has severity "info". It is not a problem; it is shown so the
  reader can see what was ignored and why.
- Values that agree produce no finding. An empty list means nothing differs.
- bounding_box = { page, x, y, width, height } as fractions 0-1 of the page.
- For invoice cases classification, reason and evidence are null; keep the current
  rendering for those.
- The list is filled once every document of the case has finished processing.

WHAT TO BUILD

A. Types (src/types/case.ts): add classification, reason, evidence to the cross-document
   finding type; add "critical" to the severity type and to every severity colour/label
   map (search for places that switch on "high").

B. Findings panel on the identity case detail page (new component, e.g.
   src/components/case/IdentityFindingsPanel.tsx), placed above the Person details
   panel from Phase 1.
   - Summary line at the top: "3 conflicts need attention - 5 differences ignored as
     harmless". When there are no findings at all: a green "All documents agree" state.
     While documents are still processing: "Checking the documents..." with a spinner.
   - Two tabs or two sections: "Needs attention" (classification conflict, sorted
     critical -> high -> medium -> low) and "Ignored as harmless" (collapsed by default).
   - One card per finding:
       * severity chip on the left
       * field label as the title (use the same labels as the Person details panel)
       * the two values side by side, each under its document type name:
             Identity card          Voter identity card
             12 March 1982          12 March 1997
         Use document_type -> label from DOCUMENT_TYPE_LABELS; show document_filename
         only as a tooltip, or inline when both documents have the same type.
       * the `description` sentence below, as given
       * a "Show on documents" button
   - Many findings can share one field (one per pair of documents). Group cards by
     field_name with a small count, so "Name" with four harmless pairs is one group that
     expands.

C. Side-by-side compare view
   - "Show on documents" opens a two-pane view: left pane the first evidence document,
     right pane the second, each scrolled to its bounding_box with the value highlighted.
     Reuse the existing overlay viewer (PDF and image) from Phase 1 for each pane.
   - Highlight colour by classification: conflict uses the severity colour, harmless
     uses a neutral grey outline. Keep the existing purple for invoice field mismatches.
   - If one side has bounding_box null, show the document without a highlight and a
     small note "Position not found on this document" above it.
   - Closing the view returns to the findings list at the same scroll position.

D. Document tabs: add a small badge on a document tab when that document is part of an
   unresolved conflict (count of conflict findings that include its id).

E. Case lists (CaseQueuePage, MyCasesPage): no change required in this phase.

UI IDEA

Severity wording and colour (plain words on screen, never the raw key):
   critical -> "Must be corrected"   red, filled chip
   high     -> "Serious mismatch"    red, outline chip
   medium   -> "Please check"        amber
   low      -> "Minor difference"    yellow / muted
   info     -> "No problem"          grey or green, with a check icon

Finding card layout:
   [chip]  Date of birth                                   [Show on documents]
           Identity card            Voter identity card
           12 March 1982            12 March 1997
           Date of birth does not match: ... The years are 15 years apart.

The two differing values are the focus: larger text than the sentence, and for names
mark the differing part in bold (a simple word-level diff is enough: bold the words that
do not appear on the other side).

Harmless section header: "Differences we ignored (5)" with one line of helper text:
"These are the same details written in a different way."

Compare view header: field label and severity chip in the centre, document type names
above each pane, a "Previous / Next finding" pair of buttons so a reviewer can step
through conflicts without going back to the list.

Text in Devanagari must render correctly in values (same font stack as Phase 1).

Do not add Accept / Dismiss buttons yet: that endpoint arrives in the next phase. Leave
a clear slot for two buttons at the bottom right of each card and of the compare view.

TEST DATA
sample-documents/identity-bundles/ground_truth.json lists, per bundle, the documents and
`expected_findings` (field, the two files, classification, reason, severity). Build mock
case responses from it; good bundles to mock: B07-dob-year-conflict (one high),
B04-name-abbreviation (five harmless, no conflict), B11-gender-and-address (two
conflicts), H01-hiring-candidate (mixed), B01-clean (none).

DONE WHEN
   - An identity case with mixed findings shows the summary, both sections, grouped
     cards and a working compare view with highlights on both panes.
   - A clean bundle shows "All documents agree".
   - An invoice case looks exactly as before.
   - npm run build and the linter pass. Tell me what you could not verify.
```

---

## Phase 4 — Review decisions and languages

```
Phase 4, frontend/ only. Two things: reviewers accept or dismiss each finding, and the
interface becomes multilingual. Do not change backend files. Invoice cases must keep
working as they do now.

BACKEND CONTRACT (live)

1. GET /cases/{id}?lang=<code>
   - top level: language, finding_counts { open, conflict_confirmed, no_issue,
     ignored_as_harmless }
   - each item of cross_document_findings now also has:
       message: { language, field_label, severity_label, summary, explanation, action,
                  text }            // identity findings only; null on invoice findings
       review_status: "pending" | "accepted" | "dismissed"
       review_note, reviewed_at, reviewed_by_name
       resolution: "open" | "conflict_confirmed" | "no_issue"
   - summary = what differs, explanation = why it matters or not, action = what to do.
     Show them as three separate lines; do not show `description` for identity findings
     any more (it is English only).

2. PATCH /cases/{id}/findings/{finding_id}?lang=<code>
   body: { "decision": "accepted" | "dismissed" | "pending", "note": string | null }
   -> { finding, finding_counts }
   - accepted = the finding is right. dismissed = it is not. pending = undo.
   - For a conflict: accepted -> resolution conflict_confirmed, dismissed -> no_issue.
   - For a harmless_variant: dismissed -> conflict_confirmed (the reviewer overrules the
     check and treats it as a real conflict).
   - 403: not a reviewer, or reviewer_l1 on a case escalated to L2. 404: unknown case or
     finding. 409: the case is already approved/rejected/closed (findings are frozen).
     422: bad decision value or note over 1000 characters.
   - Only show the controls when the case's existing `can_act` is true and the case is
     not decided.

3. GET /i18n/languages (no token needed)
   -> [{ code, name, native_name, direction: "ltr"|"rtl", source, available }]
   source: "source" (English), "google", "built_in" (Hindi finding messages without a
   Google key) or "unavailable". Offer only languages with available: true.

4. GET /i18n/catalog?lang=<code>
   -> { language, direction, fields, documents, severities, reasons, actions, no_action }
   Label maps keyed by the machine keys the case API returns (field_name, document_type,
   severity, reason). Use these for field labels, document tab names and severity chips
   instead of hard-coded English.

5. POST /i18n/translate   body: { language, texts: string[] }
   -> { language, translations: { [english]: translated }, complete }
   For the interface's own fixed strings. At most 300 strings per call, 500 characters
   each. A string that cannot be translated comes back in English.
   NEVER send user data through it (names, addresses, notes, file names): what is sent
   may go to Google.

WHAT TO BUILD

A. Language support
   - A small i18n layer: a LanguageProvider holding the current code (persist in
     localStorage, default "en"), a t("English text") function, and a language switcher.
   - Keep English strings as the keys. On language change, collect the strings the app
     uses (a central list / registry in src/lib/i18n), POST them to /i18n/translate in
     batches of at most 300, cache the result per language in localStorage, and render
     through t(). While a batch is loading, show English; never block the screen.
   - If the response has complete: false, keep English for the missing ones and do not
     retry on every render (retry on next language switch or reload).
   - Load /i18n/catalog for the same language and use it for the finding screens.
   - Pass ?lang=<code> on GET /cases/{id} and on the PATCH. Include the language in the
     TanStack Query key so switching language refetches.
   - Set <html lang> and dir from the language's `direction`. Urdu is rtl: use logical
     CSS (ms-/me-, text-start) in the components you touch so the layout mirrors.
   - Add font fallbacks for the scripts: Noto Sans plus Noto Sans Devanagari, Gujarati,
     Bengali, Gurmukhi, Tamil, Telugu, Kannada, Malayalam, Oriya, Arabic.
   - Data values (names, addresses, ID numbers, file names, notes) are never translated.

B. Review controls on each finding card and in the compare view (the slot left in
   Phase 3)
   - Conflict, pending: two buttons, "Confirm conflict" (decision accepted) and
     "Not a problem" (decision dismissed).
   - Harmless variant, pending: no buttons by default; a quiet text link
     "Treat as a real conflict" (decision dismissed).
   - Clicking opens a small inline note box (optional, 1000 characters) with Save and
     Cancel. Save sends the PATCH.
   - After a decision the card shows a status line, e.g. "Confirmed by Rita Reviewer,
     9 Oct 2026, 14:20" plus the note, and an "Undo" link (decision pending).
   - Update the card and the counts from the PATCH response (optimistic update is fine;
     roll back and show the server's `detail` on error).
   - 409 -> a notice "This case is already decided. Findings can no longer be changed."
     and hide the controls.

C. Findings panel summary uses finding_counts
   "2 need a decision - 1 confirmed - 1 cleared - 5 ignored as harmless".
   Group the list by resolution: Needs a decision (open), Confirmed conflicts, Cleared,
   Ignored as harmless (collapsed). A reviewer-overruled harmless finding appears under
   Confirmed conflicts with a small "marked by reviewer" tag.

D. Applicant view (role user, on their own case)
   - No review controls. Each open or confirmed conflict shows the three message lines,
     with the action line emphasised ("What to do").
   - A top banner: when open + conflict_confirmed > 0, "Some details do not match across
     your documents" with the count; otherwise "Your documents agree".

UI IDEA

Language switcher: a globe button in the top bar that opens a list showing native_name
with the English name in muted text ("हिन्दी  Hindi"). Also show it on the login page.

Finding card with the three-part message:

   [Serious mismatch]  Date of birth                        [Show on documents]
        Identity card            Voter identity card
        12 March 1982            12 March 1997
        Date of birth does not match: ...                       <- summary
        The years are 15 years apart.                           <- explanation, muted
        What to do: Check which document is correct ...         <- action, with an icon
        ------------------------------------------------------------------
        [Confirm conflict]   [Not a problem]

Decided card: the buttons are replaced by a coloured left border and the status line
(red for confirmed, green for cleared). Keep the two values visible.

Compare view footer: the same two buttons, and after a decision automatically move to
the next finding that still needs one. Show progress "3 of 7 decided".

Case decision panel (existing approve / reject): show a gentle hint above it while
finding_counts.open > 0: "2 findings still need a decision." Do not disable the buttons;
the backend does not block it.

TEST DATA
Same bundles as before (sample-documents/identity-bundles/ground_truth.json). For
language testing without a Google key, Hindi finding messages and the Hindi catalog work
out of the box; other languages report available: false and must not appear in the
switcher.

DONE WHEN
   - A reviewer can confirm, clear and undo findings; counts and grouping update; the
     decision survives a page reload.
   - Switching to Hindi changes the finding messages, labels and chips; interface
     strings change too when the backend has a Google key, and stay English otherwise.
   - A user (applicant) sees messages and no review controls.
   - Invoice cases look and behave exactly as before.
   - npm run build and the linter pass. Tell me what you could not verify.
```

---

## Phase 6 — Verified profile and forms (built before Phase 5)

```
Phase 6, frontend/ only. Each identity case now has a verified profile of the person,
and forms that are pre-filled from it. Do not change backend files. Use the i18n layer
from Phase 4 for every new string and pass ?lang=<code> where shown.

BACKEND CONTRACT (live)

1. GET /cases/{id}/profile
   -> { case_id, case_number, case_type, document_count, checks_complete,
        fields: [ {
          field: "full_name" | "parent_or_spouse_name" | "date_of_birth" | "gender" |
                 "address" | "annual_income",
          label,                       // English; use the Phase 4 catalog `fields` map
          status: "agreed" | "conflict" | "chosen" | "missing",
          value, display_value, latin, // null when status is conflict or missing
          document_id, document_type, document_filename,   // where the value came from
          candidates: [ { value, display_value, latin, document_id, document_type,
                          document_filename, document_ids: [...] } ],
          suggested_document_id,       // set when most documents agree, else null
          documents_to_correct: [ids]  // the documents that disagree with the majority
        } ],
        postal_code,
        id_numbers: { [document_type]: { value, display_value, document_id, ... } },
        counts: { agreed, chosen, conflict, missing },
        ready }                        // true when no detail is in conflict
   - candidates has one entry per group of agreeing documents, largest group first.
     With status agreed it has exactly one entry.
   - checks_complete false means documents are still being read; the profile can still
     change. Keep polling with the case detail query.
   - 409 for a case that is not identity_verification / hiring_verification.
   - Visible to whoever can open the case (applicant for their own case, reviewers).

2. PUT /cases/{id}/profile/{field}   body: { "document_id": "<uuid>" | null }
   -> the updated profile (same shape as 1)
   - Reviewers only, same rule as the finding buttons (case `can_act`, not decided).
   - null removes the choice.
   - 403 not a reviewer / L1 on an escalated case, 404 unknown case or field,
     409 case already decided, 422 the document is not in the case or does not state
     this detail.

3. GET /forms?case_type=<case type>&lang=<code>
   -> [ { id, title, description, case_types, field_count, prefilled_field_count,
          fields: [ { key, label, type, required, prefilled } ] } ]

4. GET /cases/{id}/forms/{form_id}?lang=<code>
   -> { case_id, case_number, checks_complete, language,
        form: { id, title, description, case_types },
        fields: [ {
          key, label, type: "text" | "textarea" | "date" | "number" | "select",
          required, prefilled,
          options?: [ { value, label } ],      // on select fields
          value, display_value,
          status: "filled" | "needs_attention" | "to_fill",
          note,                                // translated; shown under the field
          source_field, source_document_id, source_document_type,
          source_document_filename } ],
        counts: { filled, needs_attention, to_fill },
        ready }                                // false while any field needs attention
   - filled: value comes from the documents. needs_attention: the documents dispute this
     detail, value is null. to_fill: the applicant types it (note explains when a detail
     was expected but not found on the documents).
   - Dates are ISO (YYYY-MM-DD) in `value`; `display_value` is for read-only display.
   - 404 unknown form or a form for another kind of case; 409 not an identity case.
   - There is no endpoint to save or submit a filled form. Keep what the applicant types
     in component state (and optionally localStorage keyed by case + form) and offer
     Print.

WHAT TO BUILD

A. Types and API functions for the four endpoints (src/types, src/api).

B. "Verified profile" card on the identity case detail page, below the findings panel
   and above (or replacing) the per-document Person details panel from Phase 1. Keep the
   per-document panel available behind a "Per document" toggle.
   - One row per field: label, final value, and a small source line
     "from Identity card" (document type label from the catalog; file name as tooltip).
   - Status styling:
       agreed   -> value in normal text, green check
       chosen   -> value plus a tag "Chosen by reviewer"
       conflict -> no value; text "Documents do not agree" in amber/red, and the
                   candidates listed underneath as small chips:
                       [12 March 1982 - Identity card, Tax card]  [12 March 1997 - Voter card]
                   When suggested_document_id is set, mark that candidate "Most documents
                   agree" and show a line "Likely needs correction: Degree certificate"
                   built from documents_to_correct.
       missing  -> muted "Not on any document"
   - Reviewer only (can_act and case not decided): on a conflict row each candidate chip
     has a "Use this" action -> PUT with that candidate's document_id. On a chosen row
     show "Change" (reopens the candidates) and "Remove choice" (PUT null).
   - Header of the card: "Profile ready" (green) when ready, otherwise
     "2 details need to be settled" from counts.conflict. While checks_complete is
     false: "Still reading the documents...".
   - ID numbers and postal code as a compact secondary block.
   - Refetch the profile after any finding decision (Phase 4 PATCH) and after PUT,
     because clearing a finding can turn a conflict into agreed.

C. Forms
   - On the identity case page, a "Fill a form" section: cards from
     GET /forms?case_type=<this case's type> with title, description and
     "8 of 11 fields filled from your documents" (prefilled_field_count / field_count).
   - Route /cases/:id/forms/:formId -> the pre-filled form page.
       * Header: form title, case number, and a summary bar
         "7 filled - 1 needs attention - 3 for you to fill".
       * Each field rendered by `type` with its label; required fields marked.
       * filled: input pre-populated, with a small "From Identity card" source tag and
         a lock icon. Keep it editable? No: read-only, with a "why can't I edit" tooltip
         "This comes from your verified documents." (the point is that it matches them).
       * needs_attention: empty, amber border, the `note` underneath and a link
         "See the conflict" back to the findings panel of the case.
       * to_fill: normal empty input; show `note` when present.
       * select fields use `options`.
       * If ready is false: a banner at the top "Some details are in conflict. Settle
         them to complete this form." Print stays available but is labelled "Print draft".
       * Buttons: Print (window.print with a clean print stylesheet: no nav, no tags,
         fields as label/value lines) and Back to case.
   - Applicant view: same pages without any reviewer actions.

UI IDEA

Profile card row:

   Name                Ajay Prakash Sharma                         (check)
                       from Identity card
   Date of birth       Documents do not agree                      (warning)
                       [17 May 1998 - Identity card, Marksheet  Most documents agree] [Use this]
                       [17 May 1999 - Degree certificate]                              [Use this]
                       Likely needs correction: Degree certificate

Form page: a centred single column like a paper form, max width about 720px, generous
spacing, section title at the top. Source tags are small and muted so the form still
reads as a form. On mobile the summary bar sticks to the top.

Make the link between screens obvious: profile "conflict" rows and form
"needs_attention" fields both lead to the same finding in the findings panel.

TEST DATA
Same synthetic bundles. Useful cases: B01-clean (profile ready, forms fully filled),
B07-dob-year-conflict (date of birth and age need attention, one against one so no
suggestion), H01-hiring-candidate (majority suggestion, employee joining form),
B06-dob-minor-typo (no income certificate, so annual income is "to fill").

DONE WHEN
   - The profile card shows all four statuses correctly and a reviewer can choose,
     change and remove a choice.
   - Clearing a finding updates the profile and the form without a reload.
   - A form opens pre-filled, shows the three field states, works in Hindi, and prints
     cleanly.
   - Invoice cases are unchanged. npm run build and the linter pass.
   - Tell me what you could not verify.
```

---

## Phase 5 — Family

```
Phase 5, frontend/ only. A user can now set up a family, add members, and submit a
document bundle for each member. Do not change backend files. Use the Phase 4 i18n layer
for every new string and pass ?lang=<code> on the calls below.

BACKEND CONTRACT (live)

All family endpoints return the same "family view":
{
  id, name, head_user_id, language,
  members: [ {
    id, full_name,
    relation: "self" | "spouse" | "son" | "daughter" | "father" | "mother" | "other",
    relation_label,                 // translated, ready to show
    date_of_birth,                  // "YYYY-MM-DD" | null, as the head entered it
    is_head,
    latest_case_id,                 // null until a bundle was submitted for the member
    profile_ready,                  // null: no bundle yet; true: no conflict left; false
    cases: [ { id, case_number, case_type, status, created_at, document_count,
               checks_complete, open_conflicts } ]      // newest first
  } ],
  checks: [ {
    check: "member_identity" | "shared_address" | "parent_name" | "birth_order",
    label,                          // translated
    member_id, member_name, relation,
    result: "match" | "conflict" | "not_checked",
    severity: "info" | "low" | "medium" | "high" | "critical",   // meaningful on conflict
    summary                         // one translated sentence, ready to show
  } ],
  check_counts: { match, conflict, not_checked }
}

1. GET  /family?lang=            -> family view, or null when the user has none yet
2. POST /family?lang=            body { name?: string, head_date_of_birth?: "YYYY-MM-DD" }
                                 -> 201 family view. 409 if the user already has one.
3. POST /family/members?lang=    body { full_name, relation, date_of_birth? }
                                 relation is any value except "self". 201. 422 on a blank
                                 name or bad relation. 404 if no family was set up.
4. PATCH /family/members/{id}    body with any of { full_name, relation, date_of_birth }
                                 409 when changing the relation of the head's own entry.
5. DELETE /family/members/{id}   409 for the head's own entry and for a member who already
                                 has a bundle ("cannot be removed").
6. GET /families/{id}?lang=      same view, for the head or a company reviewer. 404 for
                                 anyone else.
7. POST /cases                   body { case_type, family_member_id? }
                                 Only the head of that family may pass family_member_id,
                                 and only with identity_verification or hiring_verification
                                 (422 otherwise).
8. GET /cases/{id}               now has family_member: { id, family_id, full_name,
                                 relation } | null

- Family checks are computed on every read; there is nothing to accept or dismiss.
- A check is "not_checked" when a detail is missing or still in conflict inside that
  member's own documents. It turns into match or conflict by itself once the reviewer
  settles the member's findings (Phase 4) or chooses a document (Phase 6).
- Platform admins get 403 on /family.

WHAT TO BUILD

A. "My family" page (route /family, nav item visible to company users; hide for
   platform admins).
   - Empty state when GET /family is null: a short explanation ("Add the people in your
     household and submit their documents from one place") and a "Set up my family"
     button -> a small form (family name optional, your date of birth optional) -> POST.
   - Otherwise:
       * Header: family name, "N members", and a status line from check_counts:
         "All family checks passed" / "2 things need attention" / "3 checks waiting for
         documents".
       * Member cards in a grid. Each card: avatar with initials, full_name,
         relation_label, date of birth, and a status chip:
             no bundle yet            -> grey  "No documents yet"
             bundle, checks running   -> blue  "Checking..."   (any case with
                                                checks_complete false)
             open_conflicts > 0       -> amber "2 details need attention"
             profile_ready true       -> green "Documents verified"
         Actions on the card: "Submit documents" (see B), "Open" (latest case, when
         there is one), "Fill a form" (Phase 6 forms for the latest case, when
         profile exists), Edit, Remove.
         The head's own card is first and has no Remove.
       * "Add member" card at the end of the grid -> dialog with full name, relation
         (select of the six relations, translated), date of birth (optional).
       * Edit uses the same dialog (relation disabled for the head's own entry).
       * Remove asks for confirmation; show the server's message on 409.
   - Poll GET /family while any case has checks_complete false (same interval as the
     case detail page).

B. Submitting a bundle for a member
   - "Submit documents" on a member card opens the existing new-bundle flow with the
     member preselected: create the case with case_type identity_verification and
     family_member_id, then the usual upload step.
   - On the normal New case page, when the user has a family, add an optional
     "Who is this for?" select listing the members (default: none / myself).
   - After upload, return to /family instead of the generic list.

C. Family checks panel on the My family page, below the member grid
   - Group by member (member_name with relation_label), each check as one row:
     icon by result (check / warning / clock), the `label`, and the `summary` sentence.
   - Conflicts first, coloured by severity with the Phase 4 severity chips; "not_checked"
     rows muted, collapsed under "Waiting for documents (3)".
   - A conflict row for parent_name, member_identity or shared_address links to that
     member's latest case.

D. Case detail page
   - When family_member is set, show a breadcrumb/tag at the top:
     "Tanvi Agrawal - Daughter - Agrawal family", linking to /family for the head and to
     /families/{family_id} for a reviewer.
   - Reviewer view of /families/{id}: the same page, read-only (no add, edit, remove or
     submit actions), with a "Back to case" link.

UI IDEA

Member card (about 260px wide):

   ( TA )   Tanvi Agrawal
            Daughter - born 27 Sep 2004
            [ 2 details need attention ]
            Open   Fill a form   ...

Family checks row:

   (!)  Parent's name
        Tanvi Agrawal: the documents name Mukesh Chand Agrawal as the parent. This does
        not match the parents entered in this family (Mahesh Chand Agrawal / Sarla Agrawal).
                                                                      [Open Tanvi's documents]

Keep the page calm: the member grid is the main thing, the checks panel is secondary.
On mobile the grid becomes a single column and the checks panel collapses to its header.

TEST DATA
sample-documents/identity-bundles has a ready family: F01-head (Mahesh Chand Agrawal,
born 8 Feb 1975), F01-spouse (Sarla Agrawal, 19 Jun 1978), F01-child (Tanvi Agrawal,
daughter, 27 Sep 2004). The child's two documents disagree on the father's name, so the
parent_name check is "not_checked" until that finding is settled; choosing the marksheet
makes it a conflict, choosing the identity card makes it a match. ground_truth.json has a
`families` section describing this.

DONE WHEN
   - A user can set up a family, add, edit and remove members, and submit a bundle for a
     member; the member card reflects the bundle's state.
   - Family checks show the three results, update after a finding is settled, and work
     in Hindi.
   - Another user cannot open the family; a reviewer sees it read-only.
   - Existing flows without a family are unchanged. npm run build and the linter pass.
   - Tell me what you could not verify.
```

---

## Phase 7 — Organisation by subdomain

```
Phase 7, frontend/ only. Each organisation now has its own subdomain, and sign-in on a
subdomain is limited to that organisation's users. Do not change backend files. Use the
Phase 4 i18n layer for new strings.

BACKEND CONTRACT (live)

1. Every API request should carry the header  X-Org-Subdomain: <label>
   where <label> is the organisation part of the page's host. Send it only when the page
   is on an organisation's subdomain; send nothing on the platform's own site.
   (The Vite proxy rewrites Host, so the backend cannot read it from there.)

2. GET /organisation            (no token needed)
   -> { subdomain, name, base_domain }
   - Resolved from the header (or ?subdomain=<label>).
   - On the platform's own site: subdomain and name are null.
   - 404: no active organisation uses this subdomain (also for a suspended one).

3. POST /auth/login
   - With the header, only that organisation's users can sign in. Anyone else,
     including a platform admin, gets 401 { detail: "Incorrect email or password" },
     the same as a wrong password. Do not try to tell the two apart.
   - Response now also has company_subdomain (string | null).

4. GET /auth/me  -> also company_subdomain.

5. Any authenticated request with a header that names another organisation -> 401
   "This sign-in belongs to a different organisation. Please sign in again."

6. Platform admin: GET /platform/companies items have `subdomain`.
   POST /platform/companies accepts optional `subdomain` (omitted: made from the name).
   PATCH /platform/companies/{id} accepts `subdomain`; "" or null removes it.
   409 "This subdomain is already in use." 422 when not usable (3-63 lowercase letters,
   digits or hyphens; must start and end with a letter or digit; no "--"; not a reserved
   word such as www, app, api, admin).

WHAT TO BUILD

A. src/lib/organisation.ts
   - getOrgSubdomain(): derive the label from window.location.hostname.
       * Base domain from import.meta.env.VITE_APP_BASE_DOMAIN (e.g. "example.org" or
         "localhost"). hostname === base, or "www." + base -> null.
         hostname ends with "." + base and has exactly one extra label -> that label.
       * Without the env var: treat "<label>.localhost" as an organisation, everything
         else as the platform site.
       * Labels www, app, api, admin -> null.
   - orgUrl(subdomain, path): build "<protocol>//<subdomain>.<base>[:port]<path>".
   - In src/api/client.ts add the X-Org-Subdomain header to every request when
     getOrgSubdomain() is not null.

B. App start
   - Call GET /organisation once (TanStack Query, long stale time) and keep the result in
     an OrganisationProvider.
   - 404 -> a full-page "This address is not in use" screen with the text
     "No organisation uses this address. Check the link you were given." and a link to
     the platform site (base domain) when it is known. Do not show the login form.

C. Login page
   - On an organisation's site: show the organisation name above the form
     ("Sign in to Tehsil Office, Indore") and the subdomain as small muted text.
   - On the platform's site: the current generic login. After a successful login, if
     the response has company_subdomain and it differs from the current site, redirect
     to orgUrl(company_subdomain, "/") and sign in there. Tokens are stored per origin,
     so the simplest correct behaviour is: show "Your organisation's site is
     <subdomain>.<base>. Continue there" with a button to that login page, prefilled
     with the email (pass it as ?email=). Do not pass the token or password in the URL.
   - A 401 keeps the existing "Incorrect email or password" message.

D. Session handling
   - On the 401 "different organisation" (or any 401 while signed in), clear the stored
     token and go to the login page of the current site, as the app already does for an
     expired token.
   - Show the organisation name in the top bar next to the app name (from
     OrganisationProvider, falling back to /auth/me company_name).

E. Platform admin: Companies page (src/pages/PlatformCompaniesPage.tsx)
   - New "Site address" column showing <subdomain>.<base domain> as a link (orgUrl), or
     "Not set" in muted text.
   - Create company dialog: optional "Subdomain" field with a live preview
     "indore.example.org" and helper text "Leave empty to make one from the name."
   - Edit dialog: the same field, with a "Remove" action (sends "").
   - Validate on the client with the same rule as the server and show the server's
     detail on 409 / 422.
   - Warn before changing an existing subdomain: "People using the old address will no
     longer be able to sign in there."

F. Local development note in frontend/README: run the dev server and open
   http://<subdomain>.localhost:5173 (browsers resolve *.localhost to this machine); set
   VITE_APP_BASE_DOMAIN=localhost. If Vite refuses the host, add ".localhost" to
   server.allowedHosts in vite.config.ts.

UI IDEA

Organisation login:

        [ app logo ]
        Sign in to
        Tehsil Office, Indore
        tehsil-office-indore.example.org        <- muted, small

        Email     [______________]
        Password  [______________]
        [ Sign in ]
        Language: globe switcher (Phase 4)

"Address not in use" page: centred, a neutral illustration or icon, one sentence, one
link. No form, no hint about which organisations exist.

Companies table row:   Tehsil Office, Indore | tehsil-office-indore.example.org (open) |
                       Active | 12 users | ...

DONE WHEN
   - Opening <org>.localhost:5173 shows that organisation's name on the login page, its
     users can sign in, and another organisation's user gets the normal wrong-password
     message.
   - An unknown subdomain shows the "address not in use" page.
   - Signing in on the platform site as an organisation user offers the organisation's
     own site.
   - A platform admin can set, change and remove a company's subdomain.
   - Everything still works on plain localhost:5173 with no subdomain.
   - npm run build and the linter pass. Tell me what you could not verify.
```
