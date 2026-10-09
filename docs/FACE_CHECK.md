# Photograph check — is it the same person on every document?

An identity bundle often carries the person's photograph on several documents
(identity card, voter card, driving licence, passport). This check finds the
faces on every document of a bundle and compares them pair by pair. A face that
does not look like the others is flagged like any other contradiction: with a
severity, the place on both pages, a plain sentence, and a reviewer decision.

It is **advice for a reviewer, not identification**. It never names a person,
never compares against an outside database, and a score in between is reported
as "please look", not as a verdict.

## How it works

```
upload ─► OCR + extraction ─► faces on every page ─► (all documents done) ─► compare faces ─► finding
                              YuNet finds, SFace            rules only,
                              describes (OpenCV, local)     no model call
```

1. **Reading the pages.** A PDF is rendered at 250 dpi, an image is used as is
   (enlarged if its short side is under 900 px).
2. **Finding faces.** YuNet (`face_detection_yunet_2023mar.onnx`) finds faces;
   anything narrower than 36 px or scored below 0.75 is ignored (logos, stamps,
   thumbnails too small to compare). At most the 6 largest faces are kept.
3. **Describing a face.** SFace (`face_recognition_sface_2021dec.onnx`) turns
   the aligned face into 128 numbers, stored length-1.
4. **Comparing.** When every document of the bundle has finished, each pair of
   documents that both show a face is compared by cosine similarity. **The most
   alike pair of faces decides**, so a small repeated "ghost" photograph or a
   second person on a family document does not raise a conflict by itself.
   Documents without a face (an income certificate) are left out.

Both models run on the server through OpenCV (`cv2.FaceDetectorYN`,
`cv2.FaceRecognizerSF`). They are pre-trained and unmodified: nothing is trained,
fine-tuned or sent to a cloud service.

## What the reviewer sees

| Similarity | Finding | Severity | Message (English) |
| --- | --- | --- | --- |
| ≥ 0.45 | `photo_match` (listed as ignored) | info | The photograph on the identity card and the one on the voter identity card show the same person. |
| 0.25 – 0.45 | `photo_uncertain` | medium | The photograph on the … could not be matched with the one on the … A small, blurred or older photograph can cause this. |
| < 0.25 | `photo_different_person` | critical | The photograph on the … does not look like the photograph on the … The two faces look like two different people. |

Each finding highlights the face on **both** pages (same side-by-side viewer as
every other finding) and exists in Hindi and the other interface languages. High
and critical conflicts must be accepted or dismissed before the case can be
approved (see `app/api/case_actions.py`).

## Why these thresholds

OpenCV publishes 0.363 as the same-person cut-off for SFace on clean portraits.
A photograph on a card is small, grey, printed and compressed, so the line was
re-measured on that kind of image:

* 400 photographs (40 people × 10, 64 × 64 grey, Olivetti set) were enlarged,
  placed on a card page, JPEG-compressed (quality 70) and read back through the
  real code path. Same-person pairs: 1,800; different-person pairs: 78,000.
* At 0.363, **4.1 %** of different-person pairs were wrongly accepted. At 0.45,
  **0.55 %** were, while **99.4 %** of same-person pairs still passed. Below
  0.25 sit **75.5 %** of different-person pairs and **none** of the same-person
  pairs. AUC 0.9998.
* Real portraits placed on card-style PDFs at falling quality (200 px colour →
  70 px grey, blurred, JPEG 30): same person scored 0.77 → 0.39, different
  people −0.02 → 0.30. The worst photocopy of the same person lands in "please
  look", never in "different person".

What this does **not** show: the Olivetti photographs were taken within one
session, so there is no age gap between photographs of one person. A real
old-photo/new-photo pair can score lower; that lands in "please look". No
measurement covers skin tone, age, gender or pose groups, and none was done on
real identity cards. Treat the thresholds as a starting point and re-measure on
the documents you actually receive.

## Privacy

* A face description is a **biometric template**. It is stored with the
  document (`extracted_fields.faces.items[].embedding`) and **removed from every
  API response** (`face_service.public_extracted_fields`); the browser receives
  only where each face is.
* Only synthetic documents are shipped. The photograph bundle generator
  (`scripts/generate_photo_bundles.py`) takes portraits **you supply** and are
  allowed to use; no photograph of a real person is stored in the repository.
* Decide whether storing the descriptions is lawful for your use (consent,
  retention). To switch the check off, do not install the models; it then
  reports `unavailable` and nothing else changes.

## Setup

```bash
cd backend
python -m app.services.face_models        # downloads ~39 MB into models/face (SHA-256 checked)
```

The Docker image does this at build time. `FACE_MODEL_DIR` changes the folder.
Without the models, documents are processed normally and
`extracted_fields.faces.status` is `unavailable`.

## Testing it

```bash
pytest tests/test_face_service.py                       # 22 tests; a few need the models, one needs photos
FACE_TEST_PHOTOS=DIR pytest tests/test_face_service.py  # + real-photo tests (person_a_1/2.jpg, person_b_1.jpg)

python -m scripts.generate_photo_bundles --portraits DIR --out OUT   # P01-P04 bundles + ground truth
RUN_E2E=1 E2E_PHOTO_BUNDLES=OUT pytest tests/e2e -k photograph -s    # real OCR, real LLM, real faces
```

| Bundle | What it holds | Expected |
| --- | --- | --- |
| P01 | Three cards with the same person (one a PNG scan) + income certificate | three `photo_match` |
| P02 | Identity card and a voter card carrying someone else's photograph | `photo_different_person`, critical |
| P03 | Same person, one card a poor photocopy | `photo_match` or `photo_uncertain`, never different |
| P04 | A card with no photograph | not compared |

## Limits

* Only faces the detector finds are compared: a face turned away, covered, or
  under ~36 px is skipped, and a document where nothing is found is simply not
  part of the photograph check (it is **not** reported as "photo missing").
* Heavy stamps or watermarks across the face, holograms and laminate glare
  lower the score.
* Compares photographs with photographs. It does not check that the person
  *presenting* the documents is the person in them.
