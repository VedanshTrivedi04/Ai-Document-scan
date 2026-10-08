# 🤖 Sarthi AI: Citizen Document Contradiction Telegram Bot

Sarthi is an intelligent Telegram Bot assistant built for the **AI-Based Document Contradiction Detector for Public Systems (PRAGATI02)** challenge.

It allows citizens to pre-verify their document bundles (Aadhaar, PAN, Income Certificate) directly from Telegram, identifying harmless spelling/phonetic differences versus critical contradictions before official application submission.

---

## 📂 Project Structure

```text
satyadoc-chatbot/
├── bot.py                  # Main Telegram Bot logic & state machine
├── explainer.py            # Converts technical contradiction data to citizen advice
├── verification_client.py  # Bridge to teammate's backend (+ smart mock fallback)
├── config.py               # Settings and configuration
├── requirements.txt        # Lightweight dependencies
├── .env                    # Telegram Token & Backend API URL
└── temp/                   # Storage for temporary incoming document images
```

---

## 🚀 How to Run the Bot

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Bot
```bash
python bot.py
```

Open Telegram and start chatting with **[@Sarthi_vbot](https://t.me/Sarthi_vbot)**!

---

## 🤝 Connecting to Your Friend's Verification Backend

When your friend's FastAPI server is running, simply update `.env`:
```ini
VERIFICATION_API_URL=http://localhost:8000/api/verify
MOCK_MODE=false
```

### Expected API Contract from Teammate:
```python
POST /api/verify
FormData:
  - doc1: (File)
  - doc2: (File)

Response JSON:
{
  "status": "CONTRADICTION_FOUND",
  "matches": ["Name: 'Ramesh Kumar' (Exact Match)"],
  "harmless_variants": [
    {
      "field": "address",
      "doc1_value": "Flat 201, Shanti Apts",
      "doc2_value": "#201 Shanti Apartments",
      "reason": "Abbreviation and format variation"
    }
  ],
  "conflicts": [
    {
      "field": "date_of_birth",
      "doc1_value": "14/08/1990",
      "doc2_value": "14/08/1998",
      "severity": "HIGH",
      "message": "Birth year mismatch by 8 years"
    }
  ]
}
```
If your friend's backend is not running yet, **Sarthi Bot automatically runs in smart mock mode**, allowing you to test and demo the complete user journey right away!
