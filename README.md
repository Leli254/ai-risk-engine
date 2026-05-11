# AI Risk Engine

A production-ready, payment-gated loan assessment engine built with FastAPI and OpenAI. This project implements a **Two-Pass LLM Pipeline** and **Stripe Payment Gateway** with a focus on zero-retention security and financial idempotency.

---

## 🏗️ Architectural Overview

The system is designed around the **Data Firewall** pattern. To prevent prompt injection and ensure deterministic outputs, the engine separates data extraction from risk analysis.

### Pipeline Flow

1. **Stripe Payment Gate**
   - Users initiate a request.
   - The system creates a Stripe `PaymentIntent` and waits for a secure webhook confirmation.

2. **Pass 1 (The Extractor)**
   - Once payment is confirmed, the raw application text is sent to the first LLM pass.
   - This pass extracts structured signals such as:
     - Income
     - Debt mentions
     - Sentiment
   - The extracted data is validated into a strict Pydantic model.

3. **Pass 2 (The Analyst)**
   - The second LLM pass receives **only** the structured signals.
   - It has zero access to the original raw text, physically isolating decision logic from prompt injection attacks.

---

## 🛡️ Key Engineering Features

### Zero-Retention Middleware
Custom FastAPI middleware ensures request bodies are never logged.

Only metadata such as:
- IP address
- Request path

is captured to preserve user privacy.

### Financial Idempotency
Uses:
- Stripe Idempotency Keys to prevent double charging during retries
- Internal processing tracking to avoid duplicate AI assessments

### Webhook Security
Implements `HMAC-SHA256` signature verification for all Stripe webhook events to prevent spoofing attacks.

### Rate Limiting
An in-memory sliding-window rate limiter protects the API from abuse.

The limiter is applied at the middleware layer before request bodies are read.

### Type-Safe Contracts
Built with Pydantic v2 using:
- `Decimal` for financial precision
- `Enum` for risk categories
- `frozen` models for immutability guarantees

---

## 🚀 Technical Stack

| Category | Technology |
|---|---|
| Framework | FastAPI (Python 3.10+) |
| AI | OpenAI GPT-4o-mini (Structured Outputs) |
| Payments | Stripe API |
| Validation | Pydantic v2 |
| Environment | Linux Mint / Ubuntu |

---

## 🛠️ Installation & Setup

### 1. Clone the Repository

```bash
git clone git@github.com:YOUR_USERNAME/ai-risk-engine.git
cd ai-risk-engine
```

### 2. Setup the Environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file:

```env
OPENAI_API_KEY=your_openai_key
STRIPE_SECRET_KEY=your_stripe_key
STRIPE_WEBHOOK_SECRET=your_webhook_secret
```

> Do not commit your `.env` file to version control.

### 4. Run the Server

```bash
uvicorn main:app --reload
```

---

## 🧪 Testing the Pipeline

### Create a Payment Intent

```bash
curl -X POST http://localhost:8000/payment/create \
  -H "Content-Type: application/json" \
  -d '{
    "application_id": "APP-001",
    "email": "test@example.com",
    "amount_usd": 5.00
  }'
```

### Simulate Stripe Webhook

```bash
stripe listen --forward-to localhost:8000/webhook/stripe
```

### Request Loan Assessment

```bash
curl -X POST http://localhost:8000/assess \
  -H "Content-Type: application/json" \
  -d '{
    "application_id": "APP-001",
    "text": "I earn 85,000 KES monthly. Need 500,000 KES loan for business expansion."
  }'
```

---

## 📌 Security Model

The platform follows a strict security-first architecture:

- Raw applicant text is never exposed to the decision-making model
- Request bodies are not persisted in logs
- Stripe events are cryptographically verified
- Payment and assessment operations are idempotent
- Middleware-level protections mitigate abuse before processing begins

---

## 📄 License

MIT License
