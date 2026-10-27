"""Synchronize Nested Guest OS Catalog (PRD V6): the seeded JSON's rules and the idempotent upsert."""
import copy
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from urllib.parse import urlsplit

import pytest

from common.constants.database import DbCollections, DbOperationTypes
from common.constants.nested import NESTED_MEDIA_MAX_BYTES
from common.models.agoge import NestedOsCatalogModel

from cloud_deployment import setup_manager as setup_manager_module
from cloud_deployment.operations.images_and_specs import nested_os_catalog_sync as module
from cloud_deployment.operations.images_and_specs.nested_os_catalog_sync import CATALOG_JSON, NestedOsCatalogSync
from cloud_deployment.setup_manager import SetupManager
from cloud_deployment.utilities.menu_options import SetupCategories, SetupOptions, category_menu

PROJECT = 'selected-child'
# libosinfo ids older than Windows 10 / Server 2016 (SC-40: these are never downloaded).
PRE_WINDOWS_10_OSINFO = {'win2k', 'winxp', 'win2k3', 'winvista', 'win7', 'win8', 'win8.1',
                         'win2k8', 'win2k8r2', 'win2k12', 'win2k12r2'}


class FakeDb:
    """Holds documents in memory and records every write, so a test can see that a re-sync writes nothing."""

    def __init__(self, documents=None):
        self.documents = copy.deepcopy(documents or {})
        self.writes = []

    def query(self, collection_name):
        assert collection_name == DbCollections.NESTED_OS_CATALOG
        return [copy.deepcopy(document) for document in self.documents.values()]

    def operation(self, collection_name, doc_id, operation_type, data=None):
        return collection_name, doc_id, operation_type, data

    def batch_write(self, operations):
        for collection_name, doc_id, operation_type, data in operations:
            assert (collection_name, operation_type) == (DbCollections.NESTED_OS_CATALOG, DbOperationTypes.SET)
            self.documents[doc_id] = copy.deepcopy(data)
            self.writes.append(doc_id)


def _raw_entries():
    return json.loads(CATALOG_JSON.read_text())


def _entries():
    return [NestedOsCatalogModel(**item) for item in _raw_entries()]


# --- the seeded JSON -------------------------------------------------------------------------

def test_every_json_entry_validates_and_ids_are_unique():
    entries = NestedOsCatalogSync.load_entries(CATALOG_JSON)
    assert entries
    assert len({entry.id for entry in entries}) == len(entries)


@pytest.mark.parametrize('entry', _entries(), ids=lambda entry: entry.id)
def test_downloaded_entries_have_an_https_url_and_sha256(entry):
    if entry.requires_upload:
        assert entry.media_url is None
    else:
        assert entry.media_url.startswith('https://')
        assert entry.media_sha256 and len(entry.media_sha256) == 64


@pytest.mark.parametrize('entry', _entries(), ids=lambda entry: entry.id)
def test_downloaded_entries_record_their_size_for_the_parent_disk(entry):
    # Without a size NestedHostValidator reserves the 20 GiB upload limit for the download (V6e).
    if entry.requires_upload:
        assert entry.media_size_bytes is None
    else:
        assert 0 < entry.media_size_bytes <= NESTED_MEDIA_MAX_BYTES


@pytest.mark.parametrize('entry', [entry for entry in _entries() if not entry.requires_upload],
                         ids=lambda entry: entry.id)
def test_downloaded_entries_pin_a_dated_release(entry):
    # A rolling path (current/, latest/, daily/) rotates its file, so the pinned SHA-256 would stop matching.
    segments = urlsplit(entry.media_url).path.split('/')
    assert not {'current', 'latest', 'daily'} & set(segments)


@pytest.mark.parametrize('entry', [entry for entry in _entries() if entry.install_method == 'cloud_image'],
                         ids=lambda entry: entry.id)
def test_cloud_image_entries_are_linux_disk_images_with_an_agent(entry):
    # builder.sh customize_linux installs qemu-guest-agent and writes net_config into every cloud image.
    # tar.xz is Kali's: prepare_disk converts the archive's disk.raw.
    assert entry.family == 'linux'
    assert entry.media_formats[0] in {'qcow2', 'raw', 'img.xz', 'tar.xz'}
    assert entry.net_config in {'networkd', 'netplan', 'nm-keyfile', 'ifupdown'}
    assert entry.agent is True


@pytest.mark.parametrize('entry', [entry for entry in _entries() if entry.net_config == 'nm-keyfile'],
                         ids=lambda entry: entry.id)
def test_nm_keyfile_entries_match_the_builders_rhel_family(entry):
    # Only a RHEL_FAMILY osinfo gets --selinux-relabel; unlabelled, the uploaded keyfile is ignored under enforcing SELinux.
    # Debian-based NetworkManager images (the Kali QEMU VM) run AppArmor, so they need no relabel.
    builder = (Path(__file__).parents[3] / 'cloud_functions' / 'cloud_fn_utilities' / 'server_specific' / 'nested'
               / 'builder.sh').read_text()
    rhel_family = re.search(r"^RHEL_FAMILY='([^']+)'$", builder, re.MULTILINE).group(1)
    assert re.match(rhel_family, entry.osinfo) or entry.osinfo.startswith('debian')


# Virtual disk sizes read from the pinned archives (V6b2l): Kali's tar.xz holds a 25 GiB sparse disk.raw, and its
# 7z holds a qcow2 v3 of 86,000,000,000 bytes.
ARCHIVE_VIRTUAL_SIZE_BYTES = {'kali-rolling': 26843545600, 'kali-qemu': 86000000000}


@pytest.mark.parametrize('entry_id', sorted(ARCHIVE_VIRTUAL_SIZE_BYTES))
def test_archived_disks_never_get_a_disk_gb_smaller_than_the_image(entry_id):
    # prepare_disk only grows a disk, so a smaller disk_gb would leave a guest larger than NestedHostValidator reserved.
    entry = next(entry for entry in _entries() if entry.id == entry_id)
    assert entry.min_disk_gb * 2 ** 30 >= ARCHIVE_VIRTUAL_SIZE_BYTES[entry_id]
    assert entry.default_disk_gb >= entry.min_disk_gb


@pytest.mark.parametrize('entry', [entry for entry in _entries() if entry.family == 'windows'],
                         ids=lambda entry: entry.id)
def test_windows_media_only_ever_comes_from_microsoft(entry):
    assert entry.license_note.strip()
    if entry.media_url is not None:
        host = urlsplit(entry.media_url).hostname
        assert host == 'microsoft.com' or host.endswith('.microsoft.com')


@pytest.mark.parametrize('entry', [entry for entry in _entries() if entry.osinfo in PRE_WINDOWS_10_OSINFO],
                         ids=lambda entry: entry.id)
def test_windows_older_than_10_and_2016_requires_an_upload(entry):
    assert entry.family == 'windows'
    assert entry.requires_upload is True
    assert entry.media_url is None


# Evaluation Center ISOs (V6b2n): Server editions run 180 days, Windows 11 Enterprise and LTSC 90 days.
WINDOWS_EVAL_DAYS = {'win-server-2016-eval': 180, 'win-server-2019-eval': 180, 'win-server-2022-eval': 180,
                     'win-server-2025-eval': 180, 'win-11-enterprise-eval': 90, 'win-11-ltsc-eval': 90}


def test_downloaded_windows_entries_are_the_evaluations():
    # NestedHostValidator demands a product key from any unattended Windows entry without eval_days, and an
    # evaluation ISO takes none, so a downloaded Windows entry must always carry eval_days.
    downloaded = {entry.id: entry for entry in _entries() if entry.family == 'windows' and not entry.requires_upload}
    assert {entry_id: entry.eval_days for entry_id, entry in downloaded.items()} == WINDOWS_EVAL_DAYS
    for entry in downloaded.values():
        assert entry.install_method == 'unattended_iso'
        assert entry.media_formats == ['iso']
        # Index 2 is Standard Evaluation (Desktop Experience) on the Server ISOs; the client ISO has one image.
        assert entry.windows_image_index == (2 if entry.group == 'windows_server' else 1)
    # Microsoft no longer offers a Windows 10 Enterprise evaluation, so Windows 10 stays upload-only.
    assert next(entry for entry in _entries() if entry.id == 'win-10').requires_upload is True


def test_unattended_windows_entries_carry_an_image_index_and_template():
    unattended = [entry for entry in _entries() if entry.install_method == 'unattended_iso']
    assert unattended
    for entry in unattended:
        assert entry.windows_image_index is not None
        assert entry.unattend_template == 'autounattend'


def test_load_entries_rejects_a_repeated_id(tmp_path):
    item = _raw_entries()[0]
    path = tmp_path / 'catalog.json'
    path.write_text(json.dumps([item, item]))
    with pytest.raises(ValueError, match=item['id']):
        NestedOsCatalogSync.load_entries(path)


def test_load_entries_rejects_an_invalid_entry(tmp_path):
    item = dict(_raw_entries()[0], media_url='http://example.com/x.iso', requires_upload=False)
    path = tmp_path / 'catalog.json'
    path.write_text(json.dumps([item]))
    with pytest.raises(ValueError):
        NestedOsCatalogSync.load_entries(path)


# --- sync ------------------------------------------------------------------------------------

def test_first_sync_adds_every_entry_and_a_second_sync_changes_nothing():
    db = FakeDb()
    sync = NestedOsCatalogSync(PROJECT, db=db)

    first = sync.sync()
    count = len(_raw_entries())
    assert first == {'added': count, 'updated': 0, 'unchanged': 0}
    assert set(db.documents) == {item['id'] for item in _raw_entries()}
    snapshot = copy.deepcopy(db.documents)

    db.writes.clear()
    assert sync.sync() == {'added': 0, 'updated': 0, 'unchanged': count}
    assert db.writes == []
    assert db.documents == snapshot


def test_sync_keeps_an_admins_is_enabled_choice_and_updates_the_rest():
    item = _raw_entries()[0]
    stored = dict(NestedOsCatalogModel(**item).model_dump(), is_enabled=False, display_name='stale name')
    db = FakeDb({item['id']: stored})

    report = NestedOsCatalogSync(PROJECT, db=db).sync()

    assert report['updated'] == 1
    assert db.documents[item['id']]['is_enabled'] is False
    assert db.documents[item['id']]['display_name'] == item['display_name']
    # The disabled entry is now otherwise current, so the next sync leaves it alone.
    db.writes.clear()
    NestedOsCatalogSync(PROJECT, db=db).sync()
    assert db.writes == []


def test_sync_leaves_entries_missing_from_the_json_alone():
    db = FakeDb({'admin-custom': {'id': 'admin-custom', 'display_name': 'Mine'}})
    NestedOsCatalogSync(PROJECT, db=db).sync()
    assert db.documents['admin-custom'] == {'id': 'admin-custom', 'display_name': 'Mine'}


def test_run_reports_counts(monkeypatch, capsys):
    monkeypatch.setattr(module, 'CloudEnv', Mock(return_value=SimpleNamespace(project=PROJECT)))
    assert NestedOsCatalogSync(PROJECT, db=FakeDb()).run() is True
    assert f'{len(_raw_entries())} entries added, 0 updated, 0 unchanged.' in capsys.readouterr().out


def test_run_refuses_a_mismatched_environment(monkeypatch, capsys):
    monkeypatch.setattr(module, 'CloudEnv', Mock(return_value=SimpleNamespace(project='other')))
    db = FakeDb()
    assert NestedOsCatalogSync(PROJECT, db=db).run() is False
    assert db.writes == []
    assert 'was not synchronized' in capsys.readouterr().out


def test_run_returns_false_when_the_write_fails(monkeypatch):
    monkeypatch.setattr(module, 'CloudEnv', Mock(return_value=SimpleNamespace(project=PROJECT)))
    db = FakeDb()
    db.batch_write = Mock(side_effect=RuntimeError('permission denied'))
    assert NestedOsCatalogSync(PROJECT, db=db).run() is False


def test_db_defaults_to_the_selected_projects_firestore(monkeypatch):
    factory = MagicMock()
    monkeypatch.setattr(module, 'DocumentDatabaseFactory', factory)
    assert NestedOsCatalogSync(PROJECT).db is factory.create_db_object.return_value
    assert factory.create_db_object.call_args.kwargs['project_id'] == PROJECT


# --- menu ------------------------------------------------------------------------------------

def test_menu_runs_the_catalog_sync(monkeypatch):
    operation = MagicMock()
    monkeypatch.setattr(setup_manager_module, 'NestedOsCatalogSync', operation)
    SetupManager(SetupOptions.NESTED_OS_CATALOG, PROJECT).run()
    operation.assert_called_once_with(project=PROJECT)
    operation.return_value.run.assert_called_once_with()


def test_catalog_sync_is_listed_under_images_and_specs():
    options = [option for option, _ in category_menu[SetupCategories.IMAGES_AND_SPECS]['options']]
    assert SetupOptions.NESTED_OS_CATALOG in options
    assert options[-1] == SetupOptions.BACK
