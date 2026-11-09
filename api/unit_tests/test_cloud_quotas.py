from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import DeadlineExceeded, Forbidden
from google.cloud import compute_v1

from core import cloud_quotas


PROJECT = 'training-project'
REGION = 'us-central1'


@pytest.fixture
def compute_clients(monkeypatch):
    projects = MagicMock()
    regions = MagicMock()
    monkeypatch.setattr(compute_v1, 'ProjectsClient', lambda: projects)
    monkeypatch.setattr(compute_v1, 'RegionsClient', lambda: regions)
    return projects.__enter__.return_value, regions.__enter__.return_value


def test_reads_only_lab_relevant_project_and_region_quotas(compute_clients):
    projects, regions = compute_clients
    projects.get.return_value = compute_v1.Project(quotas=[
        compute_v1.Quota(metric='NETWORKS', usage=30, limit=30),
        compute_v1.Quota(metric='FIREWALLS', usage=30, limit=100),
        compute_v1.Quota(metric='HEALTH_CHECKS', usage=1, limit=10),
    ])
    regions.get.return_value = compute_v1.Region(quotas=[
        compute_v1.Quota(metric='N2_CPUS', usage=0, limit=0),
        compute_v1.Quota(metric='CPUS', usage=18, limit=20),
        compute_v1.Quota(metric='DISKS_TOTAL_GB', usage=800, limit=1000),
        compute_v1.Quota(metric='IN_USE_ADDRESSES', usage=21, limit=20),
    ])

    snapshot = cloud_quotas.read_cloud_quotas(PROJECT, REGION)

    projects.get.assert_called_once_with(project=PROJECT, retry=None, timeout=5)
    regions.get.assert_called_once_with(project=PROJECT, region=REGION, retry=None, timeout=5)
    assert snapshot['project'] == PROJECT
    assert snapshot['region'] == REGION
    assert datetime.fromisoformat(snapshot['observed_at']).utcoffset() == timedelta(0)
    assert 'unavailable_scopes' not in snapshot
    assert snapshot['quotas'] == [
        {'metric': 'FIREWALLS', 'scope': 'global', 'usage': 30, 'limit': 100,
         'remaining': 70, 'utilization': 0.3, 'level': 'normal'},
        {'metric': 'NETWORKS', 'scope': 'global', 'usage': 30, 'limit': 30,
         'remaining': 0, 'utilization': 1, 'level': 'exhausted'},
        {'metric': 'CPUS', 'scope': REGION, 'usage': 18, 'limit': 20,
         'remaining': 2, 'utilization': 0.9, 'level': 'critical'},
        {'metric': 'DISKS_TOTAL_GB', 'scope': REGION, 'usage': 800, 'limit': 1000,
         'remaining': 200, 'utilization': 0.8, 'level': 'warning'},
        {'metric': 'IN_USE_ADDRESSES', 'scope': REGION, 'usage': 21, 'limit': 20,
         'remaining': 0, 'utilization': 1.05, 'level': 'exhausted'},
        {'metric': 'N2_CPUS', 'scope': REGION, 'usage': 0, 'limit': 0,
         'remaining': 0, 'utilization': None, 'level': 'exhausted'},
    ]


def test_project_timeout_preserves_regional_quota(compute_clients):
    projects, regions = compute_clients
    projects.get.side_effect = DeadlineExceeded('slow provider')
    regions.get.return_value = compute_v1.Region(quotas=[
        compute_v1.Quota(metric='CPUS', usage=0, limit=40),
    ])

    snapshot = cloud_quotas.read_cloud_quotas(PROJECT, REGION)

    assert snapshot['unavailable_scopes'] == ['global']
    assert [row['metric'] for row in snapshot['quotas']] == ['CPUS']


def test_incomplete_quota_values_do_not_appear_as_zero_usage(compute_clients):
    projects, regions = compute_clients
    projects.get.return_value = compute_v1.Project(quotas=[
        compute_v1.Quota(metric='NETWORKS', limit=30),
        compute_v1.Quota(metric='FIREWALLS', usage=5),
        compute_v1.Quota(metric='ROUTES', usage=float('nan'), limit=30),
        compute_v1.Quota(metric='CPUS_ALL_REGIONS', usage=-1, limit=50),
    ])
    regions.get.side_effect = Forbidden('permission denied')

    snapshot = cloud_quotas.read_cloud_quotas(PROJECT, REGION)

    assert snapshot['quotas'] == []
    assert snapshot['unavailable_scopes'] == ['global', REGION]
