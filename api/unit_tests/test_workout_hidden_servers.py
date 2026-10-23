from unittest.mock import MagicMock

import pytest

from common.models.model_validators.model_validator import ModelValidator
from common.models.agoge import WorkoutModel
from core.workout import Workout

WORKOUT = {"build_type": "unit", "id": "abcdefghij", "parent_build_type": "unit", "parent_id": "klmnopqrst"}
JUMPBOX = {"name": "jumpbox", "image": "image-jumpbox"}
KVM_HOST = {"name": "kvm-host", "image": "image-nested-hv", "hidden": True}


def _workout(doc):
    workout = object.__new__(Workout)
    workout.collection = "workout"
    workout.db = MagicMock()
    workout.db.get.return_value = doc
    workout.db.query.return_value = [doc]
    workout.workout_validator = ModelValidator(model=WorkoutModel)
    return workout


@pytest.mark.parametrize("servers,expected", [
    ([JUMPBOX, KVM_HOST], ["jumpbox"]),
    ([JUMPBOX], ["jumpbox"]),
    ([KVM_HOST], []),
])
def test_get_drops_hidden_servers(servers, expected):
    workout = _workout({**WORKOUT, "servers": [dict(server) for server in servers]}).get("abcdefghij")

    assert [server.name for server in workout.servers] == expected


def test_get_tolerates_workout_without_servers():
    assert _workout(dict(WORKOUT)).get("abcdefghij").servers is None


def test_student_list_drops_hidden_servers():
    requester = MagicMock(is_admin=False, is_authorized=True, email="student@example.com")
    doc = {**WORKOUT, "servers": [dict(JUMPBOX), dict(KVM_HOST)]}

    workouts = _workout(doc).list(requester, active=False, days=0, student=True)

    assert [server.name for server in workouts[0].servers] == ["jumpbox"]


def test_get_as_dict_keeps_hidden_servers_for_internal_callers():
    doc = {**WORKOUT, "servers": [dict(JUMPBOX), dict(KVM_HOST)]}

    workout = _workout(doc).get("abcdefghij", as_dict=True)

    assert [server["name"] for server in workout["servers"]] == ["jumpbox", "kvm-host"]
