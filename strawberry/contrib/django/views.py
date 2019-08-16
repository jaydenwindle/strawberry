import json

from django.http import HttpResponseNotAllowed, JsonResponse
from django.http.response import HttpResponseBadRequest
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

from asgiref.sync import async_to_sync
from graphql import graphql
from graphql.error import format_error as format_graphql_error
from graphql.type.schema import GraphQLSchema


class GraphQLView(View):
    schema = None

    def __init__(self, schema=None):
        assert schema, "You must pass in a schema to GraphQLView"
        assert isinstance(
            schema, GraphQLSchema
        ), "You must pass in a valid schema to GraphQLView"

        self.schema = schema

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        if request.method.lower() not in ("get", "post"):
            return HttpResponseNotAllowed(
                ["GET", "POST"], "GraphQL only supports GET and POST requests."
            )

        if "text/html" in request.META.get("HTTP_ACCEPT", ""):
            return render(
                request,
                "graphql/playground.html",
                {"REQUEST_PATH": request.get_full_path()},
            )

        data = json.loads(request.body)

        try:
            query = data["query"]
            variables = data.get("variables")
            operation_name = data.get("operationName")
        except KeyError:
            return HttpResponseBadRequest("No GraphQL query found in the request")

        context = {"request": request}

        graphql_sync = async_to_sync(graphql)

        result = graphql_sync(
            self.schema,
            query,
            variable_values=variables,
            context_value=context,
            operation_name=operation_name,
        )

        response_data = {"data": result.data}

        if result.errors:
            print(result.errors)
            response_data["errors"] = [
                format_graphql_error(err) for err in result.errors
            ]

        return JsonResponse(response_data, status=400 if result.errors else 200)
