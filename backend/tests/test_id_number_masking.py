"""Identity numbers are replaced by placeholders before the text goes to the
language model and put back afterwards (app/services/id_number_masking.py).
Every person and number here is made up."""
from unittest.mock import MagicMock

import pytest

from app.services.id_number_masking import mask_id_numbers, restore_id_numbers
from app.services.identity_documents import IDENTITY_DOCUMENT_TYPE_LABELS, extract_identity
from app.services.llm_service import FieldValue
from tests.test_identity_intake import fake_identity_analysis


@pytest.mark.parametrize(
    "printed",
    [
        "1234 5678 9012",  # national identity
        "1234-5678-9012",
        "123456789012",
        "XXXX XXXX 9012",  # already partly masked on the card
        "QWKPD4417L",  # tax identity
        "ABC1234567",  # voter identity
        "K1234567",  # passport
        "MP09 20110012345",  # driving licence
        "MP-09-2011-0012345",
    ],
)
def test_a_number_with_a_fixed_shape_is_masked(printed):
    masked, numbers = mask_id_numbers(f"Name: Asha Devi Verma\nNo: {printed}\nDOB: 12/04/1991")
    assert printed not in masked
    assert masked == "Name: Asha Devi Verma\nNo: [ID_NUMBER_1]\nDOB: 12/04/1991"
    assert numbers == [printed]


@pytest.mark.parametrize(
    "text",
    [
        "DOB: 12/04/1991",
        "Annual income: Rs. 4,80,000",
        "Indore 452001",
        "Certificate No: IC/2026/004417",  # no fixed shape: left alone
        "Mobile: 9876543210",
        "ASHA DEVI VERMA",
    ],
)
def test_other_text_is_left_alone(text):
    assert mask_id_numbers(text) == (text, [])


def test_the_same_number_gets_the_same_placeholder():
    masked, numbers = mask_id_numbers("1234 5678 9012 / QWKPD4417L / 1234 5678 9012")
    assert masked == "[ID_NUMBER_1] / [ID_NUMBER_2] / [ID_NUMBER_1]"
    assert numbers == ["1234 5678 9012", "QWKPD4417L"]


def test_restore_puts_the_numbers_back():
    numbers = ["1234 5678 9012", "QWKPD4417L"]
    reply = {
        "id_number": {"value": "[ID_NUMBER_2]", "confidence": 0.9},
        "additional_fields": [{"field_name": "linked_number", "value": "id_number_1"}],
        "confidence": 0.9,
    }
    assert restore_id_numbers(reply, numbers) == {
        "id_number": {"value": "QWKPD4417L", "confidence": 0.9},
        "additional_fields": [{"field_name": "linked_number", "value": "1234 5678 9012"}],
        "confidence": 0.9,
    }


def test_a_placeholder_the_model_made_up_becomes_no_value():
    assert restore_id_numbers({"value": "[ID_NUMBER_7]"}, ["QWKPD4417L"]) == {"value": None}


def test_the_model_never_sees_the_number_and_the_result_still_carries_it():
    llm = MagicMock()
    llm.extract_identity.return_value = fake_identity_analysis(
        id_number=FieldValue(value="[ID_NUMBER_1]", confidence=0.95, uncertain=False)
    )
    text = "Asha Devi Verma\nDOB 12/04/1991\n1234 5678 9012"

    analysis = extract_identity(llm, text)

    sent = llm.extract_identity.call_args.kwargs
    assert "1234 5678 9012" not in sent["document_text"]
    assert "[ID_NUMBER_1]" in sent["document_text"]
    assert sent["document_type_labels"] == IDENTITY_DOCUMENT_TYPE_LABELS
    assert analysis.id_number.value == "1234 5678 9012"
    assert analysis.full_name.value == "Asha Devi Verma"
