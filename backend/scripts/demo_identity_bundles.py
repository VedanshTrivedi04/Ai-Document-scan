"""
The contradiction detector on the synthetic bundles, in a terminal.

    python -m scripts.demo_identity_bundles                 # every bundle, summary table
    python -m scripts.demo_identity_bundles B07 H01         # these bundles in detail
    python -m scripts.demo_identity_bundles B07 --lang hi   # messages in Hindi
    python -m scripts.demo_identity_bundles F01 --form scholarship_application

Needs no database, queue or cloud key. It starts from what a correct reading
of each document gives (`ground_truth.json`, written by
scripts/generate_identity_bundles.py) and runs the real comparison, profile,
form and family code on it. It does NOT read the document files: OCR and
extraction are the part that needs the cloud services, and are exercised by
uploading the same files through the application.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from app.services import form_templates
from app.services.family_checks import MemberDetails, run_family_checks
from app.services.identity_comparison import BundleDocument, find_identity_contradictions
from app.services.identity_messages import DOCUMENT_LABELS, build_message
from app.services.person_profile import FindingState, ProfileDocument, build_profile

DEFAULT_TRUTH = Path(__file__).resolve().parents[2] / "sample-documents" / "identity-bundles" / "ground_truth.json"
_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _findings(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    documents = [
        BundleDocument(d["file"], d["file"], d["document_type"], d["identity_fields"]) for d in bundle["documents"]
    ]
    return find_identity_contradictions(documents)


def _key(finding: dict[str, Any]) -> tuple:
    return (finding["field_name"], tuple(finding["document_ids"]), finding["classification"], finding["reason"],
            finding["severity"].value)


def _expected(bundle: dict[str, Any]) -> set[tuple]:
    return {
        (e["field"], tuple(e["documents"]), e["classification"], e["reason"], e["severity"])
        for e in bundle["expected_findings"]
    }


def _profile(bundle: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    documents = [
        ProfileDocument(d["file"], d["file"], d["document_type"], d["identity_fields"]) for d in bundle["documents"]
    ]
    states = [
        FindingState(
            f["field_name"], tuple(f["document_ids"]),
            "no_issue" if f["classification"] == "harmless_variant" else "open",
        )
        for f in findings
    ]
    return {**build_profile(documents, states), "document_count": len(documents)}


def summary(truth: dict[str, Any]) -> bool:
    """One line per bundle; returns whether every bundle matched its ground truth."""
    print(f"{'Bundle':<34}{'Docs':>5}{'Conflicts':>11}{'Ignored':>9}   Result")
    print("-" * 72)
    all_ok, conflicts, ignored = True, 0, 0
    for bundle in truth["bundles"]:
        found = _findings(bundle)
        real = [f for f in found if f["classification"] == "conflict"]
        harmless = [f for f in found if f["classification"] == "harmless_variant"]
        ok = {_key(f) for f in found} == _expected(bundle)
        all_ok &= ok
        conflicts += len(real)
        ignored += len(harmless)
        worst = min((f["severity"].value for f in real), key=_ORDER.get, default="-")
        print(
            f"{bundle['id']:<34}{len(bundle['documents']):>5}{len(real):>11}{len(harmless):>9}   "
            f"{'as expected' if ok else 'DIFFERS FROM GROUND TRUTH'}"
            f"{'' if worst == '-' else f'  (worst: {worst})'}"
        )
    print("-" * 72)
    documents = sum(len(b["documents"]) for b in truth["bundles"])
    print(f"{len(truth['bundles'])} bundles, {documents} documents: {conflicts} conflicts flagged, "
          f"{ignored} harmless differences ignored.")
    return all_ok


def detail(bundle: dict[str, Any], language: str, form_id: str | None) -> None:
    print(f"\n=== {bundle['id']}: {bundle['title']} ===")
    for document in bundle["documents"]:
        print(f"  {document['file']:<34}{DOCUMENT_LABELS.get(document['document_type'], document['document_type'])}")
    found = sorted(_findings(bundle), key=lambda f: (_ORDER[f["severity"].value], f["field_name"]))
    if not found:
        print("\n  All documents agree.")
    for heading, classification in (("Needs attention", "conflict"), ("Ignored as harmless", "harmless_variant")):
        group = [f for f in found if f["classification"] == classification]
        if not group:
            continue
        print(f"\n  {heading} ({len(group)})")
        for finding in group:
            message = build_message(
                finding["field_name"], finding["classification"], finding["reason"], finding["severity"].value,
                finding["evidence"], finding["detail"], language,
            )
            print(f"    [{message['severity_label']}] {message['summary']}")
            print(f"        {message['explanation']}")
            if classification == "conflict":
                print(f"        -> {message['action']}")

    profile = _profile(bundle, found)
    print("\n  Verified profile")
    for field in profile["fields"]:
        if field["status"] == "conflict":
            options = " | ".join(c["display_value"] for c in field["candidates"])
            hint = ""
            if field["documents_to_correct"]:
                hint = "  (likely to correct: " + ", ".join(field["documents_to_correct"]) + ")"
            print(f"    {field['label']:<28}DISPUTED: {options}{hint}")
        elif field["status"] == "missing":
            print(f"    {field['label']:<28}not on any document")
        else:
            source = DOCUMENT_LABELS.get(field["document_type"], field["document_type"])
            print(f"    {field['label']:<28}{field['display_value']}   (from the {source})")

    form = form_templates.get_form(form_id) if form_id else None
    if form_id and (form is None or bundle["case_type"] not in form.case_types):
        print(f"\n  No form '{form_id}' for this kind of bundle.")
    elif form:
        filled = form_templates.prefill(form, profile, language=language, today=date.today())
        print(f"\n  {filled['form']['title']}  "
              f"(filled {filled['counts']['filled']}, needs attention {filled['counts']['needs_attention']}, "
              f"for the applicant {filled['counts']['to_fill']})")
        for field in filled["fields"]:
            shown = {"filled": field["display_value"], "needs_attention": "<left empty: documents disagree>",
                     "to_fill": "<to be entered>"}[field["status"]]
            print(f"    {field['label']:<36}{shown}")


def family(truth: dict[str, Any], family_id: str, language: str) -> None:
    entry = next(f for f in truth["families"] if f["id"] == family_id)
    bundles = {b["id"]: b for b in truth["bundles"]}
    members = []
    for member in entry["members"]:
        bundle = bundles[member["bundle"]]
        card = bundle["documents"][0]["identity_fields"]
        members.append(MemberDetails(
            bundle["id"], card["full_name"]["latin"], "self" if member["relation"] == "head" else
            ("daughter" if member["relation"] == "child" else member["relation"]),
            date.fromisoformat(card["date_of_birth"]["value"]), _profile(bundle, _findings(bundle)),
        ))
    print(f"\n=== Family {family_id} ===")
    for check in run_family_checks(members, language):
        print(f"  [{check['result']:<11}] {check['label']}: {check['summary']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("bundles", nargs="*", help="Bundle ids or prefixes (B07, H01, F01). None: summary of all.")
    parser.add_argument("--lang", default="en", help="Language of the messages (en, hi; others need a Google key).")
    parser.add_argument("--form", help="Also show this form pre-filled, e.g. scholarship_application.")
    parser.add_argument("--truth", type=Path, default=DEFAULT_TRUTH)
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if not args.truth.exists():
        print(f"{args.truth} not found. Run: python -m scripts.generate_identity_bundles")
        return 2
    truth = json.loads(args.truth.read_text(encoding="utf-8"))
    if not args.bundles:
        return 0 if summary(truth) else 1

    for wanted in args.bundles:
        matched = [b for b in truth["bundles"] if b["id"].lower().startswith(wanted.lower())]
        if not matched:
            print(f"No bundle starts with '{wanted}'.")
            return 2
        for bundle in matched:
            detail(bundle, args.lang, args.form)
        for entry in truth["families"]:
            if entry["id"].lower() == wanted.lower():
                family(truth, entry["id"], args.lang)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
