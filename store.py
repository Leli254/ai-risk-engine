import threading
from typing import Dict, Optional
from schemas import RiskScore


class InMemoryStore:
    """
    A thread-safe, in-memory state manager.
    Acts as an abstraction layer for idempotency and payment tracking.
    """

    def __init__(self):
        # Thread safety lock
        self._lock = threading.Lock()

        # Internal state
        self._assessments: Dict[str, RiskScore] = {}
        self._payments: Dict[str, str] = {}
        self._payment_status: Dict[str, str] = {}

    def save_assessment(self, application_id: str, score: RiskScore) -> None:
        with self._lock:
            self._assessments[application_id] = score

    def get_assessment(self, application_id: str) -> Optional[RiskScore]:
        with self._lock:
            return self._assessments.get(application_id)

    def link_payment(self, payment_intent_id: str, application_id: str) -> None:
        """Links a Stripe PaymentIntent ID to an internal Application ID."""
        with self._lock:
            self._payments[payment_intent_id] = application_id

    def set_payment_status(self, application_id: str, status: str) -> None:
        """Updates the lifecycle status (e.g., 'pending', 'paid', 'failed')."""
        with self._lock:
            self._payment_status[application_id] = status

    def get_payment_status(self, application_id: str) -> str:
        """Returns 'pending' if no status exists, ensuring a safe default."""
        with self._lock:
            return self._payment_status.get(application_id, "pending")


# Singleton instance used across the app
store = InMemoryStore()
