"""Execute features/trainer_access.feature via pytest-bdd (sync TestClient harness)."""

from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from app.assistant.tools import TOOLS, anthropic_tools

scenarios("trainer_access.feature")

_V1 = "/api/v1"


def _client(context: dict[str, object]) -> TestClient:
    """The client selected by the most recent 'logged in as ...' step."""
    client = context.get("client")
    assert isinstance(client, TestClient)
    return client


# --- background & login ---


@given("a read-only trainer account and a full-access owner account exist")
def _accounts_exist() -> None:
    pass  # conftest seeds both the owner and the trainer


@given("I am logged in as the trainer")
def _login_trainer(context: dict[str, object], trainer_client: TestClient) -> None:
    context["client"] = trainer_client


@given("I am logged in as the owner")
def _login_owner(context: dict[str, object], bdd_client: TestClient) -> None:
    context["client"] = bdd_client


# --- reads ---


@when("I open today's list")
def _open_today(context: dict[str, object]) -> None:
    context["resp"] = _client(context).get(f"{_V1}/daily/2026-06-16")


@then("I can read it")
def _can_read_it(context: dict[str, object]) -> None:
    assert context["resp"].status_code == 200


@then("I can read my workout history")
def _can_read_history(context: dict[str, object]) -> None:
    assert _client(context).get(f"{_V1}/sessions").status_code == 200


# --- writes are refused for the trainer ---


@when("the trainer tries to start a workout session")
def _trainer_start_session(context: dict[str, object]) -> None:
    context["resp"] = _client(context).post(f"{_V1}/sessions", json={"date": "2026-06-16"})


@when("the trainer tries to log wellbeing")
def _trainer_log_wellbeing(context: dict[str, object]) -> None:
    context["resp"] = _client(context).put(f"{_V1}/daily/2026-06-16/wellbeing", json={"energy": 5})


@then("the change is refused as forbidden")
def _change_forbidden(context: dict[str, object]) -> None:
    assert context["resp"].status_code == 403


# --- settings are off-limits to the trainer ---


@when("the trainer opens the settings integrations")
def _trainer_open_settings(context: dict[str, object]) -> None:
    context["resp"] = _client(context).get(f"{_V1}/settings/google-health")


@then("access is refused as forbidden")
def _access_forbidden(context: dict[str, object]) -> None:
    assert context["resp"].status_code == 403


# --- owner keeps full access ---


@when("I start a workout session")
def _owner_start_session(context: dict[str, object]) -> None:
    context["resp"] = _client(context).post(f"{_V1}/sessions", json={"date": "2026-06-16"})


@then("it is created")
def _it_is_created(context: dict[str, object]) -> None:
    assert context["resp"].status_code == 201


@then("I can read the settings integrations")
def _owner_read_settings(context: dict[str, object]) -> None:
    assert _client(context).get(f"{_V1}/settings/google-health").status_code == 200


# --- assistant chat ---


@when("the trainer sends a message to the assistant")
def _trainer_assistant_chat(context: dict[str, object]) -> None:
    context["resp"] = _client(context).post(
        f"{_V1}/assistant/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )


@then("the request is not refused as forbidden")
def _not_forbidden(context: dict[str, object]) -> None:
    # 503 (no ANTHROPIC_API_KEY) is fine; it proves the role guard let the request through.
    assert context["resp"].status_code != 403


@when("the trainer's assistant runs")
def _assistant_runs(context: dict[str, object]) -> None:
    context["read_tool_names"] = {t["name"] for t in anthropic_tools(include_writes=False)}
    context["write_tool_names"] = {t.name for t in TOOLS if t.writes}


@then("it is offered only read tools, never write tools")
def _only_read_tools(context: dict[str, object]) -> None:
    read_names = context["read_tool_names"]
    write_names = context["write_tool_names"]
    assert write_names, "expected at least one write tool to exist"
    assert isinstance(read_names, set)
    assert read_names.isdisjoint(write_names)


# --- role reporting ---


@then(parsers.parse('my role is reported as "{role}"'))
def _role_reported(context: dict[str, object], role: str) -> None:
    resp = _client(context).get(f"{_V1}/auth/me")
    assert resp.status_code == 200
    assert resp.json()["role"] == role
