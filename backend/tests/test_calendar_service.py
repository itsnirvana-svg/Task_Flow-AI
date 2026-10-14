from datetime import date

import pytest

from app.services.calendar_service import CalendarService, task_to_event


def test_task_to_event_all_day_end_is_exclusive():
    event = task_to_event(7, "Entregar informe", date(2026, 10, 31), "Versión final")
    assert event["summary"] == "Entregar informe"
    assert event["start"] == {"date": "2026-10-31"}
    assert event["end"] == {"date": "2026-11-01"}
    assert event["extendedProperties"]["private"]["taskflow_task_id"] == "7"


def test_task_to_event_without_description():
    assert task_to_event(1, "X", date(2026, 1, 1))["description"] == ""


def test_google_calls_are_not_implemented_yet():
    with pytest.raises(NotImplementedError):
        CalendarService("token").create_event({})
