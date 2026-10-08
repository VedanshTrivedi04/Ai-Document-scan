"""
The verified profile of one identity case, loaded from what is stored for it:
its documents' extracted fields, its findings with their review decisions,
and the reviewer's choices (app/services/person_profile.py builds it).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.cross_document_finding import REVIEW_PENDING, CrossDocumentFinding, finding_resolution
from app.models.document import Document, DocumentProcessingStatus
from app.services.identity_documents import is_identity_extraction
from app.services.person_profile import FindingState, ProfileDocument, build_profile
from app.services.risk_scoring_service import pipeline_status


def profile_documents(db: Session, case: Case) -> list[ProfileDocument]:
    """The case's successfully read identity documents, oldest first."""
    documents = db.execute(
        select(Document)
        .where(
            Document.case_id == case.id,
            Document.company_id == case.company_id,
            Document.processing_status == DocumentProcessingStatus.complete,
        )
        .order_by(Document.created_at, Document.id)
    ).scalars().all()
    return [
        ProfileDocument(str(d.id), d.original_filename, d.document_type, d.extracted_fields["identity_fields"])
        for d in documents
        if is_identity_extraction(d.extracted_fields)
    ]


def finding_states(db: Session, case: Case) -> list[FindingState]:
    findings = db.execute(
        select(CrossDocumentFinding).where(
            CrossDocumentFinding.case_id == case.id, CrossDocumentFinding.company_id == case.company_id
        )
    ).scalars().all()
    return [
        FindingState(
            f.field_name,
            tuple(str(i) for i in (f.document_ids or [])),
            finding_resolution(f.classification, f.review_status or REVIEW_PENDING),
        )
        for f in findings
    ]


def load_profile(db: Session, case: Case) -> dict[str, Any]:
    """The profile of an identity case, plus which case it is and whether
    its checks have finished (until then the profile may still change)."""
    documents = profile_documents(db, case)
    states = finding_states(db, case)
    return {
        "case_id": str(case.id),
        "case_number": case.case_number,
        "case_type": case.case_type.value,
        "document_count": len(documents),
        "checks_complete": pipeline_status(db, case.company_id, case.id).complete,
        "open_conflicts": sum(1 for s in states if s.resolution == "open"),
        **build_profile(documents, states, case.profile_overrides),
    }
