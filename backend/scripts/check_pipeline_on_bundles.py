"""
Runs the configured OCR and LLM providers on the synthetic identity bundles
and compares the result with the ground truth: first what was extracted from
each document, then the findings each bundle gives.

No database or queue is used: this checks the reading of documents, which is
the part that depends on the providers set in backend/.env.

    python -m scripts.check_pipeline_on_bundles              # every bundle
    python -m scripts.check_pipeline_on_bundles B07 B05      # some bundles
    python -m scripts.check_pipeline_on_bundles --ocr-only   # show the text read, no LLM
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from scripts.generate_identity_bundles import DEFAULT_OUT

from app.services.field_locator_service import attach_field_locations
from app.services.identity_comparison import BundleDocument, find_identity_contradictions
from app.services.identity_documents import extract_identity, identity_extracted_fields
from app.services.llm_service import get_llm_service
from app.services.local_ocr import LocalOCRService
from app.services.ocr_service import get_ocr_service

COMPARED = ("full_name", "parent_or_spouse_name", "date_of_birth", "gender", "address", "id_number", "annual_income")


def _same(field: str, got: dict, want: dict) -> bool:
    a, b = got.get("value"), want.get("value")
    if field in ("full_name", "parent_or_spouse_name", "address"):
        a, b = got.get("latin") or a, want.get("latin") or b
    if a in (None, "") or b in (None, ""):
        return a in (None, "") and b in (None, "")
    if isinstance(b, float):
        return isinstance(a, (int, float)) and abs(a - b) < 0.5
    squash = lambda v: "".join(ch for ch in str(v).casefold() if ch.isalnum())  # noqa: E731
    if field == "address":
        # The postal code is a field of its own; either side may also print it in the address.
        code = str(want.get("postal_code") or "")
        return squash(a).replace(code, "") == squash(b).replace(code, "") and (got.get("postal_code") or "") == code
    return squash(a) == squash(b)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("bundles", nargs="*", help="bundle ids or prefixes; default: all")
    parser.add_argument("--ocr-only", action="store_true")
    args = parser.parse_args()

    truth = json.loads((DEFAULT_OUT / "ground_truth.json").read_text(encoding="utf-8"))
    bundles = [b for b in truth["bundles"] if not args.bundles or any(b["id"].startswith(p) for p in args.bundles)]
    ocr = get_ocr_service()
    if not isinstance(ocr, LocalOCRService):
        print("This script reads files from disk and needs OCR_PROVIDER=local.")
        return 2
    llm = None if args.ocr_only else get_llm_service()

    fields_right = fields_total = bundles_right = 0
    started = time.time()
    for bundle in bundles:
        print(f"\n=== {bundle['id']} ===")
        documents = []
        for doc in bundle["documents"]:
            read = ocr.analyze_bytes((DEFAULT_OUT / bundle["id"] / doc["file"]).read_bytes())
            if args.ocr_only:
                print(f"--- {doc['file']} ({len(read.pages[0].words)} words)\n{read.text}")
                continue
            try:
                analysis = extract_identity(llm, read.text)
            except Exception as exc:  # noqa: BLE001 - report and carry on
                print(f"  {doc['file']}: extraction FAILED: {exc}")
                fields_total += len(COMPARED)
                continue
            stored = identity_extracted_fields(analysis)
            located = attach_field_locations(read.pages, stored)
            wrong = []
            for field in COMPARED:
                fields_total += 1
                got, want = stored["identity_fields"][field], doc["identity_fields"][field]
                if _same(field, got, want):
                    fields_right += 1
                else:
                    wrong.append(f"{field}: got {got.get('latin') or got.get('value')!r}, "
                                 f"expected {want.get('latin') or want.get('value')!r}")
            type_note = "" if analysis.document_type == doc["document_type"] else f"  [type: {analysis.document_type}]"
            print(f"  {doc['file']:<32} {len(COMPARED) - len(wrong)}/{len(COMPARED)} fields, {located} located{type_note}")
            for line in wrong:
                print(f"      {line}")
            documents.append(BundleDocument(doc["file"], doc["file"], analysis.document_type, stored["identity_fields"]))
        if args.ocr_only:
            continue
        got_findings = {(f["field_name"], tuple(f["document_ids"]), f["classification"], f["severity"].value)
                        for f in find_identity_contradictions(documents)}
        want_findings = {(e["field"], tuple(e["documents"]), e["classification"], e["severity"])
                         for e in bundle["expected_findings"]}
        ok = got_findings == want_findings
        bundles_right += ok
        print(f"  findings: {'as expected' if ok else 'DIFFER'}"
              f" ({sum(1 for g in got_findings if g[2] == 'conflict')} conflicts,"
              f" {sum(1 for g in got_findings if g[2] != 'conflict')} harmless)")
        for item in sorted(want_findings - got_findings):
            print(f"      missing: {item}")
        for item in sorted(got_findings - want_findings):
            print(f"      extra:   {item}")

    if not args.ocr_only:
        print(f"\nFields read correctly: {fields_right}/{fields_total}. "
              f"Bundles with the expected findings: {bundles_right}/{len(bundles)}. "
              f"Time: {time.time() - started:.0f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
