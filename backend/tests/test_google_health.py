"""Live Google Health client — pure parsing of the v4 API payloads (no network)."""

from datetime import date

from app.integrations.health import GoogleHealthProvider, _parse_sleep, _sum_steps


def test_sum_steps_countsum() -> None:
    body = {"rollupDataPoints": [{"steps": {"countSum": 733}}, {"steps": {"count": 100}}]}
    assert _sum_steps(body) == 833


def test_sum_steps_empty() -> None:
    assert _sum_steps({}) == 0


def test_parse_sleep_longest_session() -> None:
    # Times in UTC; +12h offset (NZ) -> local 23:20 bedtime, 07:22 wake on 2026-05-25.
    body = {
        "dataPoints": [
            {
                "sleep": {
                    "interval": {
                        "startTime": "2026-05-24T11:20:00Z",
                        "endTime": "2026-05-24T19:22:00Z",
                        "startUtcOffset": "43200s",
                        "endUtcOffset": "43200s",
                    },
                    "stages": [
                        {
                            "type": "LIGHT",
                            "startTime": "2026-05-24T11:20:00Z",
                            "endTime": "2026-05-24T15:57:00Z",
                        },
                        {
                            "type": "DEEP",
                            "startTime": "2026-05-24T15:57:00Z",
                            "endTime": "2026-05-24T17:08:00Z",
                        },
                        {
                            "type": "REM",
                            "startTime": "2026-05-24T17:08:00Z",
                            "endTime": "2026-05-24T19:12:00Z",
                        },
                        {
                            "type": "AWAKE",
                            "startTime": "2026-05-24T19:12:00Z",
                            "endTime": "2026-05-24T19:22:00Z",
                        },
                    ],
                }
            }
        ]
    }
    rec = _parse_sleep(body)
    assert rec is not None
    assert rec.date == date(2026, 5, 25)
    assert rec.bedtime == "23:20"
    assert rec.wake_time == "07:22"
    assert rec.asleep_min == 472.0  # light 277 + deep 71 + rem 124
    assert rec.efficiency == 97.9  # 472 / 482


def test_parse_sleep_empty() -> None:
    assert _parse_sleep({"dataPoints": []}) is None


async def test_provider_unconfigured_raises() -> None:
    import pytest

    from app.integrations.health import IntegrationNotConfigured

    with pytest.raises(IntegrationNotConfigured):
        await GoogleHealthProvider().fetch(date(2026, 5, 25), date(2026, 5, 25))
