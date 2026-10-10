"""Contradictions between one person's documents count toward the case's risk
(identity.* rules, app/services/risk_rule_seed.py). Before these rules a case
whose two cards named different people scored 0 and sat at "low"."""
import pytest

from app.models.case import CaseType, RiskTier
from app.models.cross_document_finding import REVIEW_DISMISSED, CrossDocumentFinding, FindingSeverity
from app.models.user import User, UserRole
from app.services.risk_rule_seed import IDENTITY_RULES, SIGNATURE_RULES, seed_risk_rules
from app.services.risk_scoring_service import score_case
from tests.helpers_risk import add_cross_doc_event, add_document, make_case


@pytest.fixture()
def user(db_session):
    u = User(email="applicant@x.com", hashed_password="x", role=UserRole.user, is_active=True)
    db_session.add(u)
    db_session.commit()
    seed_risk_rules(db_session, db_session.info["test_company_id"])
    db_session.commit()
    return u


def _case_with(db_session, user, *findings):
    case = make_case(db_session, user)
    case.case_type = CaseType.identity_verification
    add_document(db_session, case, user, "id.pdf")
    add_document(db_session, case, user, "voter.pdf")
    add_cross_doc_event(db_session, case)
    for field_name, severity, classification, reason in findings:
        db_session.add(CrossDocumentFinding(
            company_id=db_session.info["test_company_id"], case_id=case.id, field_name=field_name,
            finding_type="identity_consistency", classification=classification, reason=reason,
            severity=FindingSeverity(severity), description=f"{field_name} differs.", document_ids=[],
        ))
    db_session.commit()
    return case


def _score(db_session, case):
    return score_case(db_session, db_session.info["test_company_id"], case.id)


@pytest.mark.parametrize(
    "field_name, severity, rule_id, tier",
    [
        ("full_name", "critical", "identity.name_different_person", RiskTier.high),
        ("photo", "critical", "identity.photo_different_person", RiskTier.high),
        ("date_of_birth", "high", "identity.dob_year_mismatch", RiskTier.medium),
        ("gender", "high", "identity.gender_mismatch", RiskTier.medium),
        ("annual_income", "critical", "identity.income_far_apart", RiskTier.medium),
        ("full_name", "medium", "identity.name_possible_error", RiskTier.low),
        ("photo", "medium", "identity.photo_uncertain", RiskTier.low),
    ],
)
def test_a_conflict_scores_by_what_it_suggests(db_session, user, field_name, severity, rule_id, tier):
    case = _case_with(db_session, user, (field_name, severity, "conflict", "x"))
    assessment = _score(db_session, case)
    assert [r["rule_id"] for r in assessment.triggered_reasons] == [rule_id]
    assert assessment.tier == tier


def test_harmless_and_minor_differences_do_not_score(db_session, user):
    case = _case_with(
        db_session, user,
        ("full_name", "info", "harmless_variant", "spelling_variant"),
        ("photo", "info", "harmless_variant", "photo_match"),
        ("date_of_birth", "low", "conflict", "date_day_month_swapped"),
        ("address", "low", "conflict", "address_difference"),
    )
    assessment = _score(db_session, case)
    assert assessment.score == 0 and assessment.tier == RiskTier.low


def test_a_dismissed_conflict_no_longer_counts(db_session, user):
    case = _case_with(db_session, user, ("full_name", "critical", "conflict", "different_name"))
    assert _score(db_session, case).tier == RiskTier.high
    row = db_session.query(CrossDocumentFinding).filter_by(case_id=case.id).one()
    row.review_status = REVIEW_DISMISSED
    db_session.commit()
    assert _score(db_session, case).tier == RiskTier.low


def test_every_identity_rule_is_seeded_once(db_session, user):
    from app.models.risk_rule import RiskRule

    ids = [r.rule_id for r in db_session.query(RiskRule).filter(RiskRule.rule_id.like("identity.%"))]
    assert sorted(ids) == sorted(r["rule_id"] for r in [*IDENTITY_RULES, *SIGNATURE_RULES])


def test_going_back_to_an_earlier_state_makes_that_assessment_the_latest_again(db_session, user):
    """Dismissing a conflict (or removing the reference signature) returns the
    evidence to a state that was scored before; the case must show that score again."""
    from app.services.risk_scoring_service import latest_assessment

    case = _case_with(db_session, user)
    assert _score(db_session, case).score == 0
    row = CrossDocumentFinding(
        company_id=db_session.info["test_company_id"], case_id=case.id, field_name="full_name",
        finding_type="identity_consistency", classification="conflict", reason="different_name",
        severity=FindingSeverity.critical, description="x", document_ids=[],
    )
    db_session.add(row)
    db_session.commit()
    assert _score(db_session, case).tier == RiskTier.high
    row.review_status = REVIEW_DISMISSED
    db_session.commit()
    _score(db_session, case)
    latest = latest_assessment(db_session, db_session.info["test_company_id"], case.id)
    assert latest.score == 0 and latest.tier == RiskTier.low
    assert case.risk_tier == RiskTier.low
