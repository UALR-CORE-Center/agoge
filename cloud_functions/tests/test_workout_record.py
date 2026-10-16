"""build_workout_record (shared by the Cloud Function and the API's CTF teams) and the
BaseUnit._create_workout_record wrapper that delegates to it."""
from unittest.mock import MagicMock

import pytest

from cloud_fn_utilities.course_objects.unit import base_unit as base_unit_module
from cloud_fn_utilities.course_objects.unit.base_unit import BaseUnit
from common.constants.build_constants import BuildConstants
from common.constants.states import WorkoutStates
from common.models.agoge import UnitModel
from common.utilities.timestamps import Timestamps
from common.utilities import workout_record as workout_record_module
from common.utilities.workout_record import build_workout_record

EXPIRES = 1893456000.0


def unit_model(**overrides) -> UnitModel:
    data = {
        "id": "unitaaaaaa", "version": "1", "instructor_id": ["gm@example.edu"], "build_type": "unit",
        "unit_type": "solo",
        "summary": {"name": "Web Lab", "description": "A lab", "student_instructions_url": "https://x/instr"},
        "workspace_settings": {"count": 1, "expires": EXPIRES},
        "servers": [{"name": "web", "image": "img"}],
        **overrides,
    }
    return UnitModel(**data)


def test_record_is_a_not_built_workout_of_the_unit():
    record = build_workout_record(unit_model(), "wkaaaaaaaa", log_name="test")

    assert record["id"] == "wkaaaaaaaa"
    assert record["parent_id"] == "unitaaaaaa"
    assert record["state"] == WorkoutStates.NOT_BUILT.value
    assert record["build_type"] == BuildConstants.BuildType.WORKOUT
    assert record["parent_build_type"] == BuildConstants.BuildType.UNIT
    assert record["summary"]["name"] == "Web Lab"
    assert record["summary"]["student_instructions_url"] == "https://x/instr"
    assert record["expires"] == EXPIRES
    assert [s["name"] for s in record["servers"]] == ["web"]


def test_shutoff_timestamp_is_set_only_when_the_unit_has_servers():
    with_servers = build_workout_record(unit_model(), "wkaaaaaaaa", log_name="test")
    without = build_workout_record(unit_model(servers=None), "wkaaaaaaaa", log_name="test")

    assert with_servers["shutoff_timestamp"] > Timestamps.get_current_timestamp_utc()
    assert without["shutoff_timestamp"] is None
    assert not without["servers"]


def test_student_email_is_lowercased_and_other_kwargs_pass_through():
    record = build_workout_record(
        unit_model(), "wkaaaaaaaa", log_name="test", student_email="Student@X.EDU", team_name="Red",
    )
    assert record["student_email"] == "student@x.edu"
    assert record["team_name"] == "Red"


def test_workout_duration_days_overrides_the_unit_expiry():
    record = build_workout_record(unit_model(workout_duration_days=2), "wkaaaaaaaa", log_name="test")

    expected = Timestamps.get_current_timestamp_utc(add_seconds=2 * 86400)
    assert record["expires"] == pytest.approx(expected, abs=5)
    assert record["expires"] != EXPIRES


@pytest.mark.parametrize("test, expected", [(True, True), (False, None)])
def test_test_flag_is_set_on_the_record_handed_to_the_validator(monkeypatch, test, expected):
    # WorkoutModel has no `test` field, so the flag is only visible before validation (as it always was).
    validator = MagicMock()
    monkeypatch.setattr(workout_record_module, "ModelValidator", validator)

    build_workout_record(unit_model(), "wkaaaaaaaa", log_name="test", test=test)

    [record] = validator.return_value.load.call_args.args
    assert record.get("test") is expected


def test_web_applications_get_a_url():
    unit = unit_model(web_applications=[{"name": "App", "host_name": "app.example", "starting_directory": "login"}])
    [app] = build_workout_record(unit, "wkaaaaaaaa", log_name="test")["web_applications"]
    assert app["url"] == "https://app.example/login"


def _base_unit(unit, debug):
    obj = object.__new__(type('ConcreteUnit', (BaseUnit,), {name: None for name in BaseUnit.__abstractmethods__}))
    obj.unit_model = unit
    obj.debug = debug
    obj.log_name = "test"
    return obj


@pytest.mark.parametrize("debug", [True, False])
def test_base_unit_record_equals_the_shared_builder_and_follows_debug(debug, monkeypatch):
    monkeypatch.setattr(Timestamps, "get_current_timestamp_utc", classmethod(lambda cls, **kw: 1000.0))
    unit = unit_model()
    obj = _base_unit(unit, debug)

    record = obj._create_workout_record("wkaaaaaaaa", student_email="S@x.edu", student_name="S")
    expected = build_workout_record(unit, "wkaaaaaaaa", log_name="test", test=debug, student_email="S@x.edu", student_name="S")

    assert record == expected
    assert record["student_email"] == "s@x.edu"


def test_base_unit_passes_debug_as_the_test_flag_to_the_validator(monkeypatch):
    validator = MagicMock()
    monkeypatch.setattr(workout_record_module, "ModelValidator", validator)

    _base_unit(unit_model(), True)._create_workout_record("wkaaaaaaaa")

    assert validator.return_value.load.call_args.args[0]["test"] is True


def test_base_unit_delegates_with_its_unit_log_name_and_debug_flag(monkeypatch):
    delegate = MagicMock(return_value={"id": "x"})
    monkeypatch.setattr(base_unit_module, "build_workout_record", delegate)
    unit = unit_model()
    obj = _base_unit(unit, True)

    assert obj._create_workout_record("wkaaaaaaaa", team_name="Red") == {"id": "x"}
    delegate.assert_called_once_with(unit, "wkaaaaaaaa", log_name="test", test=True, team_name="Red")
