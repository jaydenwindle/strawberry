from strawberry.asgi.constants import (
    GQL_COMPLETE,
    GQL_CONNECTION_ACK,
    GQL_CONNECTION_INIT,
    GQL_CONNECTION_TERMINATE,
    GQL_DATA,
    GQL_START,
    GQL_STOP,
)


def test_simple_subscription(schema, test_client):
    with test_client.websocket_connect("/", "graphql-ws") as ws:
        ws.send_json({"type": GQL_CONNECTION_INIT})
        ws.send_json(
            {
                "type": GQL_START,
                "id": "demo",
                "payload": {"query": "subscription { example }"},
            }
        )

        response = ws.receive_json()
        assert response["type"] == GQL_CONNECTION_ACK

        response = ws.receive_json()
        assert response["type"] == GQL_DATA
        assert response["id"] == "demo"
        assert response["payload"]["data"] == {"example": "Hi"}

        ws.send_json({"type": GQL_STOP, "id": "demo"})
        response = ws.receive_json()
        assert response["type"] == GQL_COMPLETE
        assert response["id"] == "demo"

        ws.send_json({"type": GQL_CONNECTION_TERMINATE})
