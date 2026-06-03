"""Execute features/measurements.feature via pytest-bdd (sync TestClient harness)."""

from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("measurements.feature")

_M = "/api/v1/measurements"


@given("I am logged in")
def _logged_in() -> None:
    pass  # bdd_client carries a valid token


@when(parsers.parse("I record measurements for {d}:"))
def _record_table(
    bdd_client: TestClient, context: dict[str, object], d: str, datatable: list[list[str]]
) -> None:
    body: dict[str, object] = {"date": d}
    for metric, value in datatable[1:]:  # skip header row
        body[metric] = float(value)
    assert bdd_client.post(_M, json=body).status_code == 200
    context["date"] = d


@then(parsers.parse("they are saved against {d}"))
def _saved_against(bdd_client: TestClient, d: str) -> None:
    rows = bdd_client.get(_M).json()
    assert any(r["date"] == d for r in rows)


@when(parsers.parse("I record only weight_kg {value} for {d}"))
def _record_weight_only(
    bdd_client: TestClient, context: dict[str, object], value: str, d: str
) -> None:
    assert bdd_client.post(_M, json={"date": d, "weight_kg": float(value)}).status_code == 200
    context["date"] = d


@then(parsers.parse("weight is saved for {d}"))
def _weight_saved(bdd_client: TestClient, d: str) -> None:
    assert bdd_client.get(f"{_M}/{d}").json()["weight_kg"] is not None


@then("the other metrics are left blank for that date")
def _others_blank(bdd_client: TestClient, context: dict[str, object]) -> None:
    row = bdd_client.get(f"{_M}/{context['date']}").json()
    assert row["waist_cm"] is None


@given(parsers.parse("I recorded {metric} {value} on {d}"))
def _recorded(
    bdd_client: TestClient, context: dict[str, object], metric: str, value: str, d: str
) -> None:
    assert bdd_client.post(_M, json={"date": d, metric: float(value)}).status_code == 200
    context["last"] = {"date": d, "metric": metric}


@when(parsers.parse("I record {metric} {value} on {d}"))
def _record(
    bdd_client: TestClient, context: dict[str, object], metric: str, value: str, d: str
) -> None:
    assert bdd_client.post(_M, json={"date": d, metric: float(value)}).status_code == 200
    context["date"] = d


@then(
    parsers.parse("the {d} entry shows a change of {delta} cm on waist since the previous reading")
)
def _change(bdd_client: TestClient, d: str, delta: str) -> None:
    row = bdd_client.get(f"{_M}/{d}").json()
    assert row["changes"]["waist_cm"] == float(delta)


@given("I have several weeks of waist_cm measurements")
def _several(bdd_client: TestClient) -> None:
    for d, w in (("2026-05-11", 99), ("2026-05-18", 98), ("2026-05-25", 96)):
        bdd_client.post(_M, json={"date": d, "waist_cm": w})


@when("I view the waist trend")
def _view_trend(bdd_client: TestClient, context: dict[str, object]) -> None:
    context["trend"] = bdd_client.get(_M).json()


@then("I see waist plotted over time")
def _trend_present(context: dict[str, object]) -> None:
    trend = context["trend"]
    assert isinstance(trend, list)
    assert len([r for r in trend if r["waist_cm"] is not None]) >= 2


@when(parsers.parse("I open the detail for {d}"))
def _open_detail(bdd_client: TestClient, context: dict[str, object], d: str) -> None:
    context["detail"] = bdd_client.get(f"{_M}/{d}").json()


@then(parsers.parse("the detail shows waist_cm {value}"))
def _detail_shows(context: dict[str, object], value: str) -> None:
    detail = context["detail"]
    assert isinstance(detail, dict)
    assert detail["waist_cm"] == float(value)


@when(parsers.parse("I correct it to {value}"))
def _correct(bdd_client: TestClient, context: dict[str, object], value: str) -> None:
    last = context["last"]
    assert isinstance(last, dict)
    bdd_client.post(_M, json={"date": last["date"], last["metric"]: float(value)})


@then(parsers.parse("the {d} weight reads {value}"))
def _weight_reads(bdd_client: TestClient, d: str, value: str) -> None:
    assert bdd_client.get(f"{_M}/{d}").json()["weight_kg"] == float(value)


@then("no duplicate entry is created")
def _no_duplicate(bdd_client: TestClient, context: dict[str, object]) -> None:
    last = context["last"]
    assert isinstance(last, dict)
    rows = bdd_client.get(_M).json()
    assert len([r for r in rows if r["date"] == last["date"]]) == 1
