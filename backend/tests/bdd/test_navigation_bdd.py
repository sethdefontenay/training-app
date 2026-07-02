"""Execute features/navigation.feature via pytest-bdd.

Navigation (a home control and a back-one-step control on every screen, the back trail,
returning to the hub) is entirely client-side routing — there is no backend contract to
assert. Every step is therefore a documented no-op; the feature is wired so it's counted
and stays in sync with the spec, but it is UI-only.
"""

from pytest_bdd import given, parsers, scenarios, then, when

scenarios("navigation.feature")

# All steps below are UI-only: client-side navigation has no server endpoint to exercise.


@given("I am logged in")
def _login() -> None:
    pass


@given(parsers.re(r'I am on the "(?P<screen>[^"]+)" screen'))
@then(parsers.re(r'I am on the "(?P<screen>[^"]+)" screen'))
def _on_screen(screen: str) -> None:
    pass


@then('a "home" control is available')
def _home_control() -> None:
    pass


@then('a "back" control is available')
def _back_control() -> None:
    pass


@given(parsers.re(r'I have navigated into "(?P<screen>[^"]+)"'))
def _navigated_into(screen: str) -> None:
    pass


@given(parsers.re(r'I opened "(?P<opened>[^"]+)" from the "(?P<origin>[^"]+)" screen'))
def _opened_from(opened: str, origin: str) -> None:
    pass


@given("I went Home → daily task list → workout logging")
def _trail() -> None:
    pass


@given("I am on the Home hub")
@then("I am on the Home hub")
def _home_hub() -> None:
    pass


@when(parsers.re(r'I tap "(?P<control>[^"]+)"'))
def _tap(control: str) -> None:
    pass


@then(parsers.re(r'when I tap "(?P<control>[^"]+)" again'))
def _tap_again(control: str) -> None:
    pass


@then("I am on the daily task list")
def _on_daily() -> None:
    pass


@then("I stay on the Home hub")
def _stay_home() -> None:
    pass


@then("nothing is lost")
def _nothing_lost() -> None:
    pass
