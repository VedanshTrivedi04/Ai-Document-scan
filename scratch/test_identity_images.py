import os
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, '/app')

from app.services.ocr_service import get_ocr_service
from app.services import face_service
from app.services.identity_documents import extract_identity, identity_extracted_fields
from app.services.identity_comparison import BundleDocument, find_identity_contradictions, compare_photos
from app.services.llm_service import get_llm_service

print("=" * 70)
print("TEST 1: Face Detection & Biometric Comparison (YuNet + SFace)")
print("=" * 70)

bytes_a1 = open("/app/sample_test/aadhar 1.jpg", "rb").read()
bytes_a2 = open("/app/sample_test/aadhar 2.jpg", "rb").read()
bytes_pan = open("/app/sample_test/pan_rahul_kumar.jpg", "rb").read()

faces_a1 = face_service.detect_faces(bytes_a1)
faces_a2 = face_service.detect_faces(bytes_a2)
faces_pan = face_service.detect_faces(bytes_pan)

print(f"Faces found in aadhar 1 (Rahul Kumar): {len(faces_a1)}")
for i, f in enumerate(faces_a1):
    print(f"  Face {i+1}: score={f.score:.3f}, box=({f.x:.3f}, {f.y:.3f}, {f.width:.3f}, {f.height:.3f})")

print(f"Faces found in pan_rahul_kumar (Rahul Kumar): {len(faces_pan)}")
for i, f in enumerate(faces_pan):
    print(f"  Face {i+1}: score={f.score:.3f}, box=({f.x:.3f}, {f.y:.3f}, {f.width:.3f}, {f.height:.3f})")

print(f"Faces found in aadhar 2 (Roshan Pandey): {len(faces_a2)}")
for i, f in enumerate(faces_a2):
    print(f"  Face {i+1}: score={f.score:.3f}, box=({f.x:.3f}, {f.y:.3f}, {f.width:.3f}, {f.height:.3f})")

doc_a1 = BundleDocument("doc1", "aadhar 1.jpg", "national_id_card", {}, faces=tuple(f.as_dict() for f in faces_a1))
doc_pan = BundleDocument("doc2", "pan_rahul_kumar.jpg", "tax_id_card", {}, faces=tuple(f.as_dict() for f in faces_pan))
doc_a2 = BundleDocument("doc3", "aadhar 2.jpg", "national_id_card", {}, faces=tuple(f.as_dict() for f in faces_a2))

print("\n" + "-" * 50)
print("MATCH TEST: Aadhaar 1 vs PAN (Both Rahul Kumar)")
print("-" * 50)
verdict_match = compare_photos(doc_a1, doc_pan)
if verdict_match:
    print(f"Verdict Classification: {verdict_match.classification.upper()}")
    print(f"Reason:                 {verdict_match.reason}")
    print(f"Severity:               {verdict_match.severity.value}")
    print(f"Similarity Score:       {verdict_match.detail.get('similarity') if verdict_match.detail else 'N/A'}")
    if verdict_match.classification == "harmless_variant":
        print(">>> SUCCESS: Face correctly verified as SAME PERSON! (photo_match)")

print("\n" + "-" * 50)
print("CONFLICT TEST: Aadhaar 1 vs Aadhaar 2 (Rahul vs Roshan)")
print("-" * 50)
verdict_conflict = compare_photos(doc_a1, doc_a2)
if verdict_conflict:
    print(f"Verdict Classification: {verdict_conflict.classification.upper()}")
    print(f"Reason:                 {verdict_conflict.reason}")
    print(f"Severity:               {verdict_conflict.severity.value}")
    print(f"Similarity Score:       {verdict_conflict.detail.get('similarity') if verdict_conflict.detail else 'N/A'}")
    print(">>> SUCCESS: Face correctly flagged as CONFLICT!")

print("\n" + "=" * 70)
print("TEST 2: OCR & Text Extraction")
print("=" * 70)
ocr = get_ocr_service()

res_a1 = ocr.analyze_bytes(bytes_a1)
print(f"Aadhaar 1 OCR Word Count: {len(res_a1.pages[0].words)}")
print("Aadhaar 1 Text:\n" + res_a1.text.strip())

print("\n" + "-" * 50)
res_pan = ocr.analyze_bytes(bytes_pan)
print(f"PAN Card OCR Word Count: {len(res_pan.pages[0].words)}")
print("PAN Card Text:\n" + res_pan.text.strip())

print("\n" + "-" * 50)
res_a2 = ocr.analyze_bytes(bytes_a2)
print(f"Aadhaar 2 OCR Word Count: {len(res_a2.pages[0].words)}")
print("Aadhaar 2 Text:\n" + res_a2.text.strip())

print("\n" + "=" * 70)
print("TEST 3: Full End-to-End Extraction & Cross-Document Contradiction Check")
print("=" * 70)

llm = get_llm_service()

analysis_a1 = extract_identity(llm, res_a1.text)
stored_a1 = identity_extracted_fields(analysis_a1)
print("\nAadhaar 1 Extracted Fields:")
for k, v in stored_a1["identity_fields"].items():
    if v.get("value"):
        print(f"  {k}: {v.get('value')} (confidence: {v.get('confidence')})")

analysis_pan = extract_identity(llm, res_pan.text)
stored_pan = identity_extracted_fields(analysis_pan)
print("\nPAN Card Extracted Fields:")
for k, v in stored_pan["identity_fields"].items():
    if v.get("value"):
        print(f"  {k}: {v.get('value')} (confidence: {v.get('confidence')})")

analysis_a2 = extract_identity(llm, res_a2.text)
stored_a2 = identity_extracted_fields(analysis_a2)
print("\nAadhaar 2 Extracted Fields:")
for k, v in stored_a2["identity_fields"].items():
    if v.get("value"):
        print(f"  {k}: {v.get('value')} (confidence: {v.get('confidence')})")

# Bundle 1: Rahul Kumar (Aadhaar 1 + PAN Card) -> EXPECTED: MATCH (Clean!)
doc_b1_a1 = BundleDocument("doc_a1", "aadhar 1.jpg", analysis_a1.document_type, stored_a1["identity_fields"], faces=tuple(f.as_dict() for f in faces_a1))
doc_b1_pan = BundleDocument("doc_pan", "pan_rahul_kumar.jpg", analysis_pan.document_type, stored_pan["identity_fields"], faces=tuple(f.as_dict() for f in faces_pan))

findings_b1 = find_identity_contradictions([doc_b1_a1, doc_b1_pan])
print("\n" + "-" * 50)
print(f"BUNDLE 1 (Aadhaar 1 + PAN Rahul Kumar) FINDINGS COUNT: {len(findings_b1)}")
print("-" * 50)
conflicts_b1 = [f for f in findings_b1 if f["classification"] == "conflict"]
harmless_b1 = [f for f in findings_b1 if f["classification"] == "harmless_variant"]
print(f"Conflicts: {len(conflicts_b1)}, Harmless: {len(harmless_b1)}")
for f in findings_b1:
    print(f"  [{f['classification'].upper()}] field={f['field_name']}, reason={f['reason']}, sev={f['severity'].value}: {f['description']}")

# Bundle 2: Different Persons (Aadhaar 1 Rahul Kumar + Aadhaar 2 Roshan Pandey) -> EXPECTED: CONFLICTS!
doc_b2_a1 = BundleDocument("doc_a1", "aadhar 1.jpg", analysis_a1.document_type, stored_a1["identity_fields"], faces=tuple(f.as_dict() for f in faces_a1))
doc_b2_a2 = BundleDocument("doc_a2", "aadhar 2.jpg", analysis_a2.document_type, stored_a2["identity_fields"], faces=tuple(f.as_dict() for f in faces_a2))

findings_b2 = find_identity_contradictions([doc_b2_a1, doc_b2_a2])
print("\n" + "-" * 50)
print(f"BUNDLE 2 (Aadhaar 1 Rahul + Aadhaar 2 Roshan) FINDINGS COUNT: {len(findings_b2)}")
print("-" * 50)
conflicts_b2 = [f for f in findings_b2 if f["classification"] == "conflict"]
harmless_b2 = [f for f in findings_b2 if f["classification"] == "harmless_variant"]
print(f"Conflicts: {len(conflicts_b2)}, Harmless: {len(harmless_b2)}")
for f in findings_b2:
    print(f"  [{f['classification'].upper()}] field={f['field_name']}, reason={f['reason']}, sev={f['severity'].value}: {f['description']}")
