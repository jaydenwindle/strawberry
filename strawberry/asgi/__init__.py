import typing

from graphql import graphql
from graphql.language import parse
from graphql.error import format_error as format_graphql_error
from graphql.subscription import subscribe
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket, WebSocketState

from .constants import (
    GQL_COMPLETE,
    GQL_CONNECTION_ACK,
    GQL_CONNECTION_INIT,
    GQL_CONNECTION_TERMINATE,
    GQL_DATA,
    GQL_START,
    GQL_STOP,
)


class GraphQL:
    def __init__(self, schema, playground: bool = True) -> None:
        self.schema = schema
        self.playground = playground

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            await self.handle_http(scope=scope, receive=receive, send=send)
        elif scope["type"] == "websocket":
            await self.handle_websocket(scope=scope, receive=receive, send=send)
        else:
            raise ValueError("Unknown scope type: %r" % (scope["type"],))

    async def handle_websocket(self, scope: Scope, receive: Receive, send: Send):
        websocket = WebSocket(scope=scope, receive=receive, send=send)

        await websocket.accept(subprotocol="graphql-ws")

        while websocket.application_state != WebSocketState.DISCONNECTED:
            message = await websocket.receive_json()

            operation_id = message.get("id")
            message_type = message.get("type")

            if message_type == GQL_CONNECTION_INIT:
                await websocket.send_json({"type": GQL_CONNECTION_ACK})
            elif message_type == GQL_CONNECTION_TERMINATE:
                await websocket.close()
            elif message_type == GQL_START:
                await self.start_subscription(
                    message.get("payload"), operation_id, websocket
                )
            elif message_type == GQL_STOP:
                await websocket.close()

    async def start_subscription(self, data, operation_id: str, websocket: WebSocket):
        query = data["query"]
        variables = data.get("variables")
        operation_name = data.get("operation_name")

        data = await subscribe(
            self.schema,
            parse(query),
            variable_values=variables,
            operation_name=operation_name,
            # TODO: context
            context_value=None,
        )

        async for result in data:
            # TODO: send errors if any

            await self._send_message(
                websocket, GQL_DATA, {"data": result.data}, operation_id
            )

        await self._send_message(websocket, GQL_COMPLETE, None, operation_id)
        await websocket.close()

    async def _send_message(
        self,
        websocket: WebSocket,
        type_: str,
        payload: typing.Any = None,
        operation_id: str = None,
    ) -> None:
        data = {"type": type_}

        if operation_id is not None:
            data["id"] = operation_id

        if payload is not None:
            data["payload"] = payload

        return await websocket.send_json(data)

    async def handle_http(self, scope: Scope, receive: Receive, send: Send) -> Response:
        request = Request(scope=scope, receive=receive)

        if request.method == "POST":
            content_type = request.headers.get("Content-Type", "")

            if "application/json" in content_type:
                data = await request.json()
            elif "application/graphql" in content_type:
                body = await request.body()
                text = body.decode()
                data = {"query": text}
            else:
                return PlainTextResponse(
                    "Unsupported Media Type",
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                )
        else:
            return PlainTextResponse(
                "Method Not Allowed", status_code=status.HTTP_405_METHOD_NOT_ALLOWED
            )

        try:
            query = data["query"]
            variables = data.get("variables")
            operation_name = data.get("operationName")
        except KeyError:
            return PlainTextResponse(
                "No GraphQL query found in the request",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        context = {"request": request}

        result = await self.execute(
            query, variables=variables, context=context, operation_name=operation_name
        )

        response_data = {"data": result.data}

        if result.errors:
            response_data["errors"] = [
                format_graphql_error(err) for err in result.errors
            ]

        status_code = (
            status.HTTP_400_BAD_REQUEST if result.errors else status.HTTP_200_OK
        )

        response = JSONResponse(response_data, status_code=status_code)

        await response(scope, receive, send)

    async def execute(self, query, variables=None, context=None, operation_name=None):
        return await graphql(
            self.schema,
            query,
            variable_values=variables,
            operation_name=operation_name,
            context_value=context,
        )
