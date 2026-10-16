from unittest.mock import MagicMock

from common.constants.users import LMSConnection
from common.models.users import AgogeUser, APISettings
from core.users import Users


def test_every_lms_connection_is_a_usable_settings_key():
    assert all(isinstance(lms.value, str) for lms in LMSConnection)


def test_user_without_settings_gets_an_empty_entry_per_lms():
    user = AgogeUser(uid="uid", email="user@example.edu")

    assert set(user.settings) == {lms.value for lms in LMSConnection}
    assert all(settings == APISettings() for settings in user.settings.values())


def test_reset_user_settings_clears_the_named_lms():
    stored = AgogeUser(
        uid="uid", email="user@example.edu",
        settings={"canvas": APISettings(api="key", url="https://canvas.example.edu", secret="secret")},
    )
    users = object.__new__(Users)
    users.get_user = MagicMock(return_value=stored)
    users._update_user = MagicMock()

    users.reset_user_settings(stored, user_id="uid", data={"canvas": True})

    assert stored.settings["canvas"] == APISettings()
    users._update_user.assert_called_once_with(stored)
