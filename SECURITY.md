# Security Policy

## Security Philosophy

AI Risk Engine is designed with a security-first architecture focused on:
- Prompt injection isolation
- Financial idempotency
- Minimal data retention
- Strict validation boundaries
- Deterministic structured processing

The platform follows a layered defensive approach to reduce attack surface and protect sensitive financial workflows.

---

# Supported Versions

Only the latest stable release of AI Risk Engine receives security updates and vulnerability fixes.

Older versions may contain unpatched vulnerabilities and should not be used in production environments.

---

# Reporting a Vulnerability

Please do not publicly disclose security vulnerabilities.

If you discover a security issue, report it responsibly through one of the following methods:

- Open a private GitHub Security Advisory
- Contact the maintainers directly through a private channel

Include the following information where possible:
- Vulnerability description
- Reproduction steps
- Potential impact
- Affected components
- Relevant logs or request samples
- Suggested mitigations (optional)

We will investigate all valid reports promptly.

---

# Security Design Principles

## Data Firewall Architecture

The platform uses a two-pass processing pipeline to isolate untrusted raw applicant text from downstream decision logic.

### Pass 1 — Extraction Layer
The first model pass:
- Receives raw applicant input
- Extracts structured financial signals
- Produces validated deterministic output

### Pass 2 — Analysis Layer
The second model pass:
- Receives only validated structured data
- Has zero access to the original raw text
- Operates within constrained decision boundaries

This separation reduces prompt injection risk and limits unintended model influence.

---

# Request Data Handling

To minimize sensitive data exposure:

- Raw request bodies are not persisted in logs
- Middleware avoids logging sensitive payload content
- Only operational metadata may be retained for diagnostics

Examples of retained metadata may include:
- Request path
- Timestamp
- Response status
- Client IP address

The application is designed to minimize unnecessary data retention whenever possible.

---

# Payment Security

The payment pipeline uses multiple safeguards:

## Stripe Signature Verification

All Stripe webhook events are verified using:
- HMAC-SHA256 signature validation
- Timestamp validation
- Secret-based webhook authentication

Unsigned or invalid events are rejected.

---

## Financial Idempotency

To prevent duplicate processing:
- Stripe Idempotency Keys are used for payment creation
- Internal request tracking prevents repeated assessments
- Duplicate webhook events are safely ignored where applicable

---

# Input Validation

The platform uses strict schema validation through Pydantic v2.

Validation protections include:
- Typed request contracts
- Enum-constrained categories
- Decimal-based financial values
- Immutable/frozen internal models

Invalid or malformed payloads are rejected before business processing begins.

---

# Rate Limiting

The API includes middleware-level rate limiting to reduce abuse risk.

Protections are applied before request bodies are processed to:
- Reduce unnecessary resource consumption
- Limit automated abuse attempts
- Protect downstream AI and payment systems

---

# Dependency Security

Dependencies should be regularly audited and updated.

Recommended practices:
- Pin dependency versions
- Monitor upstream advisories
- Review transitive dependency changes
- Apply security updates promptly

---

# Secrets Management

Sensitive credentials must never be committed to version control.

This includes:
- OpenAI API keys
- Stripe secret keys
- Webhook signing secrets
- Production environment credentials

Use environment variables or a secure secrets manager for deployment.

---

# Production Deployment Recommendations

For production deployments, the following are strongly recommended:

- HTTPS/TLS termination
- Reverse proxy protection
- Structured logging with sensitive field filtering
- External rate limiting (e.g., Redis-backed)
- Centralized monitoring and alerting
- Isolated secrets management
- Containerized deployment
- Regular dependency scanning

---

# Scope Limitations

This project is provided as an educational and engineering reference implementation.

The maintainers make no guarantees regarding:
- Regulatory compliance
- Financial approval accuracy
- Legal suitability for production lending decisions
- Compliance with jurisdiction-specific lending laws

Organizations deploying this software are responsible for:
- Regulatory review
- Compliance validation
- Operational security hardening
- Independent risk assessment

---

# Responsible Disclosure

We appreciate responsible disclosure practices that help improve the safety and reliability of the project.

Please avoid:
- Public disclosure before remediation
- Automated exploitation attempts
- Disruptive testing against public infrastructure

Thank you for helping improve the security of AI Risk Engine.
