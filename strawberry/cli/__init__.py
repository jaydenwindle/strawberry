import click
import sys

import os
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware

import importlib

import uvicorn

import hupper

from strawberry.contrib.starlette import GraphQLApp, GraphQLSubscriptionApp


@click.group()
def run():
    pass


@run.command("server")
@click.argument("module", type=str)
@click.option("-h", "--host", default="0.0.0.0", type=str)
@click.option("-p", "--port", default=8000, type=int)
@click.option("--disable-logs", is_flag=True)
def server(module, host, port, disable_logs):
    sys.path.append(os.getcwd())

    reloader = hupper.start_reloader("strawberry.cli.run", verbose=False)

    schema_module = importlib.import_module(module)

    reloader.watch_files([schema_module.__file__])

    app = Starlette(debug=True)

    app.add_middleware(
        CORSMiddleware, allow_headers=["*"], allow_origins=["*"], allow_methods=["*"]
    )

    app.add_route(
        "/graphql", GraphQLApp(schema_module.schema, logging=not disable_logs)
    )
    app.add_websocket_route("/graphql", GraphQLSubscriptionApp(schema_module.schema))

    if not disable_logs:
        print(f"Running strawberry on http://{host}:{port}/graphql 🍓")

    uvicorn.run(app, host=host, port=port, log_level="error")
