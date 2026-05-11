from fastapi.testclient import TestClient
from main import app, store

client = TestClient(app)


def test_webhook_updates_payment_status(mocker):
    # Define the payload that Stripe would send
    payload_data = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "metadata": {"application_id": "TEST-APP-123"}
            }
        }
    }

    # Create a mock that mimics the Stripe Event object behavior
    mock_event = mocker.Mock()
    mock_event.type = "payment_intent.succeeded"
    # Ensure both dict conversion methods are covered
    mock_event.to_dict.return_value = payload_data
    mock_event.to_dict_recursive.return_value = payload_data

    mocker.patch("main.verify_webhook_signature", return_value=mock_event)

    # Execute the request
    # Note: store is persistent in memory, so ensure key is unique or reset
    response = client.post(
        "/webhook/stripe",
        json={"id": "evt_test"},
        headers={"stripe-signature": "t=123,v1=abc"}
    )

    # Assertions
    assert response.status_code == 200
    assert store.get_payment_status("TEST-APP-123") == "paid"
