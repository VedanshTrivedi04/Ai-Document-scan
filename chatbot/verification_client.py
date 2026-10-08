"""
verification_client.py: Bridge between Sarthi Telegram Bot and the verification backend.
Supports multi-document bundles (up to 5 documents: Aadhaar, PAN, Income Cert, Ration Card, Address proof).
"""

import httpx
import logging
from pathlib import Path
from typing import Dict, Any, List
from config import VERIFICATION_API_URL, MOCK_MODE

logger = logging.getLogger(__name__)

async def verify_documents(doc_paths: List[Path]) -> Dict[str, Any]:
    """
    Sends a list of document files (bundle of 2 to 5 documents) to the backend.
    Falls back to smart mock mode if backend is unreachable or MOCK_MODE is enabled.
    """
    if not MOCK_MODE:
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                files = []
                file_handles = []
                try:
                    for idx, path in enumerate(doc_paths):
                        f = open(path, "rb")
                        file_handles.append(f)
                        files.append(("docs", (path.name, f, "image/jpeg")))

                    response = await client.post(VERIFICATION_API_URL, files=files)
                    if response.status_code == 200:
                        return response.json()
                    else:
                        logger.warning(f"Backend returned status {response.status_code}: {response.text}")
                finally:
                    for f in file_handles:
                        f.close()
        except Exception as e:
            logger.warning(f"Could not connect to backend ({e}). Using smart mock fallback.")

    # Smart Multi-Document Bundle Mock Result
    return get_smart_bundle_mock_result(len(doc_paths))

def get_smart_bundle_mock_result(total_docs: int) -> Dict[str, Any]:
    """
    Returns realistic multi-document bundle contradiction findings:
    Demonstrating cross-document checks across up to 5 documents.
    """
    return {
        "status": "CONTRADICTION_FOUND",
        "total_documents_scanned": total_docs,
        "scanned_documents": [
            "Document 1: Aadhaar Card (Identity Proof)",
            "Document 2: PAN Card (Financial ID)",
            "Document 3: Income Certificate / Aay Praman Patra",
            "Document 4: Ration Card / Family ID",
            "Document 5: Electricity Bill (Address Proof)"
        ][:total_docs],
        "matches": [
            "Applicant Name: 'Ramesh Kumar' (Aadhaar, PAN & Ration Card me match hai)",
            "Father's Name: 'Dinesh Kumar' (Aadhaar & PAN me match hai)",
            "Gender: 'Male' (Sabhi dastavejon me match hai)"
        ],
        "harmless_variants": [
            {
                "field": "Applicant Name (Spelling / Initials)",
                "doc1": "Income Certificate ('Ramesh K.')",
                "doc2": "Aadhaar Card ('Ramesh Kumar')",
                "reason": "Harmless Initial Expansion (K. -> Kumar). Is wajah se aavedan reject nahi hoga."
            },
            {
                "field": "Address Format",
                "doc1": "Aadhaar ('Flat 201, Shanti Apts, MG Road, Indore')",
                "doc2": "Electricity Bill ('#201 Shanti Apartments, M.G. Marg, Indore - 452001')",
                "reason": "Format & abbreviation variation ('Road' vs 'Marg'). Locality aur PIN code dono me match hain."
            }
        ],
        "conflicts": [
            {
                "field": "Date of Birth (DOB)",
                "doc1_name": "Aadhaar Card",
                "doc1_value": "14/08/1990",
                "doc2_name": "Income Certificate",
                "doc2_value": "14/08/1998",
                "severity": "HIGH",
                "message": "Janm Varsh (Birth Year) me 8 saal ka bada farak hai (1990 vs 1998). Scheme eligibility prabhavit ho sakti hai."
            },
            {
                "field": "Annual Income (Aay)",
                "doc1_name": "Self Declaration / Ration Card",
                "doc1_value": "₹ 60,000 / varsh (BPL Quota)",
                "doc2_name": "Tehsildar Income Certificate",
                "doc2_value": "₹ 1,80,000 / varsh",
                "severity": "HIGH",
                "message": "Declared income aur certified income me antar hai. BPL subsidy raddh ho sakti hai."
            }
        ]
    }
