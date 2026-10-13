"""Tracing stays off: the guard, the runners, and importing the graph package (no network)."""

import os
import subprocess
import sys

import pytest

from cta.eval import run_answers, run_retrieval
from cta.settings import TRACING_VARIABLES, enabled_tracing, refuse_tracing


def test_tracing_is_not_enabled_in_the_test_environment():
    assert enabled_tracing(dict(os.environ)) == []
    for name in TRACING_VARIABLES:
        assert os.environ.get(name, "").lower() not in ("true", "1", "yes")


@pytest.mark.parametrize("name", TRACING_VARIABLES)
@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes"])
def test_each_tracing_variable_is_detected(name, value):
    assert enabled_tracing({name: value}) == [name]
    with pytest.raises(RuntimeError, match=name):
        refuse_tracing({name: value})


def test_false_or_empty_values_are_not_tracing():
    assert enabled_tracing({"LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": ""}) == []
    refuse_tracing({})


@pytest.mark.parametrize("module", [run_answers, run_retrieval])
def test_the_eval_runners_refuse_to_start_with_tracing_on(module, monkeypatch, capsys):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    code = module.main(["x", "--split", "dev", "--label", "never-written-label"])
    assert (
        code == 2 and "refused: tracing is enabled (LANGSMITH_TRACING)" in capsys.readouterr().out
    )


def test_importing_the_graph_package_makes_no_network_call():
    script = (
        "import socket\ndef no(*a, **k):\\n    raise AssertionError('network call at import')\n"
    ).replace("\\n", "\n") + (
        "socket.socket.connect = no\n"
        "socket.create_connection = no\n"
        "socket.getaddrinfo = no\n"
        "import cta.graph, langgraph.graph\n"
        "import cta.graph.build\n"
    )
    env = {k: v for k, v in os.environ.items() if k not in TRACING_VARIABLES}
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr


def test_importing_the_api_stack_and_serving_in_process_makes_no_network_call():
    """fastapi brings opentelemetry-api (API only, no exporter): it must send nothing out."""
    script = (
        "import socket\n"
        "def no(*a, **k):\n"
        "    raise AssertionError('network call')\n"
        "socket.socket.connect = no\n"
        "socket.create_connection = no\n"
        "socket.getaddrinfo = no\n"
        "import fastapi, starlette, uvicorn, opentelemetry.trace as t\n"
        "from fastapi.testclient import TestClient\n"
        "app = fastapi.FastAPI()\n"
        "app.get('/x')(lambda: {'ok': 1})\n"
        "assert TestClient(app).get('/x').json() == {'ok': 1}\n"
        "assert type(t.get_tracer_provider()).__name__ == 'ProxyTracerProvider'\n"
    )
    env = {k: v for k, v in os.environ.items() if k not in TRACING_VARIABLES}
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
