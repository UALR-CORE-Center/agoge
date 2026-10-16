import os
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cloud_fn_utilities.course_objects.compute import lab_server_manager as lab_server_module
from common.utilities.ctf_plant_contract import (
    LINUX_LOADER,
    LINUX_LOADER_METADATA_KEY,
    WINDOWS_LOADER,
    WINDOWS_LOADER_METADATA_KEY,
)


LabServerManager = lab_server_module.LabServerManager

CUSTOM_SCRIPT = "#!/bin/bash\necho custom > /tmp/custom-marker\n"
GUACAMOLE_SCRIPT = "#!/bin/bash\necho guacamole-setup\n"
ASSESSMENT_SCRIPT = {'key': 'startup-script', 'value': "#! /bin/bash\nexport BUILD_ID=abcdefghij\n"}
WINDOWS_SPEC_PS1 = "Write-Output 'spec ps1'\n"


def _manager(metadata=None, startup_script=None, guacamole_startup_script=None, assessment=None):
    # Build only what _add_metadata reads; the real __init__ needs GCP and Firestore.
    manager = object.__new__(LabServerManager)
    manager.server_spec = SimpleNamespace(
        name="abcdefghij-web",
        metadata=metadata,
        ssh_keys=[],
        startup_script=startup_script,
        guacamole_startup_script=guacamole_startup_script,
    )
    manager.assessment = MagicMock()
    manager.assessment.get_startup_scripts.return_value = assessment
    return manager


def _items(manager):
    manager._add_metadata()
    return manager.server_spec.metadata['items']


def _value(items, key):
    matches = [item for item in items if item['key'] == key]
    assert len(matches) == 1, f"expected exactly one {key} item, got {len(matches)}"
    return matches[0]['value']


def test_existing_startup_and_assessment_scripts_are_kept_with_the_loader_appended_last():
    items = _items(_manager(
        startup_script=CUSTOM_SCRIPT,
        guacamole_startup_script=GUACAMOLE_SCRIPT,
        assessment=dict(ASSESSMENT_SCRIPT),
    ))

    script = _value(items, LINUX_LOADER_METADATA_KEY)
    custom_at = script.index("echo custom")
    guacamole_at = script.index("echo guacamole-setup")
    assessment_at = script.index("export BUILD_ID=abcdefghij")
    loader_at = script.index(LINUX_LOADER.strip())
    # The loader runs after every other boot script, so it plants into a fully set-up server.
    assert custom_at < guacamole_at < assessment_at < loader_at
    assert script.rstrip().endswith(LINUX_LOADER.strip())


def test_spec_metadata_startup_script_is_kept_with_the_loader_appended():
    items = _items(_manager(metadata={'items': [
        {'key': 'startup-script', 'value': CUSTOM_SCRIPT},
        {'key': 'enable-oslogin', 'value': 'FALSE'},
    ]}))

    script = _value(items, LINUX_LOADER_METADATA_KEY)
    assert script.startswith(CUSTOM_SCRIPT.rstrip())
    assert script.rstrip().endswith(LINUX_LOADER.strip())
    assert _value(items, 'enable-oslogin') == 'FALSE'


def test_server_with_no_scripts_gets_both_loaders():
    items = _items(_manager())

    assert _value(items, LINUX_LOADER_METADATA_KEY) == LINUX_LOADER
    assert _value(items, WINDOWS_LOADER_METADATA_KEY) == WINDOWS_LOADER


def test_spec_windows_ps1_script_is_concatenated_with_the_windows_loader_not_overwritten():
    items = _items(_manager(metadata=[{'key': 'windows-startup-script-ps1', 'value': WINDOWS_SPEC_PS1}]))

    script = _value(items, WINDOWS_LOADER_METADATA_KEY)
    assert script.startswith(WINDOWS_SPEC_PS1.rstrip())
    assert script.rstrip().endswith(WINDOWS_LOADER.strip())


def test_merge_concatenates_two_windows_ps1_scripts():
    items = []
    LabServerManager._merge_metadata_item(items, {'key': 'windows-startup-script-ps1', 'value': "Write-Output 'one'\n"})
    LabServerManager._merge_metadata_item(items, {'key': 'windows-startup-script-ps1', 'value': "Write-Output 'two'"})

    assert items == [{'key': 'windows-startup-script-ps1', 'value': "Write-Output 'one'\nWrite-Output 'two'"}]


def test_merge_still_overwrites_non_script_keys():
    items = []
    LabServerManager._merge_metadata_item(items, {'key': 'enable-oslogin', 'value': 'TRUE'})
    LabServerManager._merge_metadata_item(items, {'key': 'enable-oslogin', 'value': 'FALSE'})

    assert items == [{'key': 'enable-oslogin', 'value': 'FALSE'}]


def test_windows_assessment_bat_script_is_untouched_by_the_ps1_loader():
    bat = {'key': 'windows-startup-script-bat', 'value': 'setx /m BUILD_ID abcdefghij\n'}
    items = _items(_manager(assessment=dict(bat)))

    assert _value(items, 'windows-startup-script-bat') == bat['value']
    assert _value(items, WINDOWS_LOADER_METADATA_KEY) == WINDOWS_LOADER


def test_loaders_already_in_spec_metadata_are_not_duplicated():
    # Metadata copied from a server built after D4 already ends with both loaders.
    built = _items(_manager(startup_script=CUSTOM_SCRIPT))
    rebuilt = _items(_manager(metadata={'items': [dict(item) for item in built]}))

    assert _value(rebuilt, LINUX_LOADER_METADATA_KEY).count(LINUX_LOADER.strip()) == 1
    assert _value(rebuilt, WINDOWS_LOADER_METADATA_KEY).count(WINDOWS_LOADER.strip()) == 1


def test_existing_startup_script_with_null_value_does_not_break_the_merge():
    items = _items(_manager(metadata={'items': [{'key': 'startup-script', 'value': None}]}))

    assert _value(items, LINUX_LOADER_METADATA_KEY).strip() == LINUX_LOADER.strip()


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_concatenated_startup_script_runs_the_original_script_and_then_the_loader(tmp_path):
    # Shows the concatenation is a working script, not just the right text: the original
    # script's side effect happens and the loader then fetches and runs the plant.
    original_marker = tmp_path / "original"
    plant_marker = tmp_path / "planted"
    original = f"#!/bin/bash\necho original > {original_marker}\n"
    items = _items(_manager(startup_script=original))
    script_path = tmp_path / "startup-script.sh"
    script_path.write_text(_value(items, LINUX_LOADER_METADATA_KEY))

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_curl = bin_dir / "curl"
    # Writes a plant payload to the -o target, as the metadata server would.
    fake_curl.write_text(
        "#!/bin/bash\n"
        "while [ $# -gt 0 ]; do\n"
        "  if [ \"$1\" = \"-o\" ]; then out=\"$2\"; shift; fi\n"
        "  shift\n"
        "done\n"
        f"printf 'echo planted > {plant_marker}\\n' > \"$out\"\n"
    )
    fake_curl.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "TMPDIR": str(tmp_path)}

    result = subprocess.run(["bash", str(script_path)], env=env, capture_output=True, text=True, timeout=30)

    assert result.returncode == 0
    assert original_marker.read_text().strip() == "original"
    assert plant_marker.read_text().strip() == "planted"
    assert result.stdout == ""
