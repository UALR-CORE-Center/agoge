import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from api.core.project import Project
from common.exceptions import BadRequest


class _Environment:
    def __init__(self, values):
        self.values = values

    def get_env(self):
        return self.values


class ProjectWireGuardSettingsTest(unittest.TestCase):
    def test_gcp_project_id_cannot_be_patched(self) -> None:
        project = object.__new__(Project)
        project.env = _Environment({
            'project': 'tenant-project',
            'wireguard_dns_prefix': 'wg',
        })
        project.db = Mock()
        project.logger = Mock()

        with self.assertRaisesRegex(BadRequest, 'immutable'):
            project.update(
                requester=SimpleNamespace(uid='admin'),
                data={'project': 'different-project'},
            )

        project.db.update.assert_not_called()


if __name__ == '__main__':
    unittest.main()
