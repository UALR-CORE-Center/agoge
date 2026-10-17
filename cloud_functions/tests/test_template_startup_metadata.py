"""V4: a template server's image startup_script and its user-creation script share one metadata key."""
from types import SimpleNamespace

from cloud_fn_utilities.course_objects.compute.image_template_manager import ImageTemplateManager
from cloud_fn_utilities.course_objects.compute.lab_server_manager import LabServerManager
from cloud_fn_utilities.server_specific.agoge_user_startup_script import MetadataKey

IMAGE_SCRIPT = '#!/bin/bash\necho image-custom-script'
USER = {'username': 'agoge', 'password': 'S3cret!', 'ssh_key': 'ssh-ed25519 AAAA test'}


def _metadata(os, startup_script=None, human_interaction=None, ssh_keys=None):
    manager = object.__new__(ImageTemplateManager)
    manager.server_spec = SimpleNamespace(
        os=os, startup_script=startup_script, human_interaction=human_interaction, ssh_keys=ssh_keys,
    )
    manager._add_metadata()
    return manager.server_spec.metadata['items']


def _values(items, key):
    return [item['value'] for item in items if item['key'] == key]


def test_linux_template_gets_one_startup_script_holding_both_scripts():
    items = _metadata('linux', startup_script=IMAGE_SCRIPT, human_interaction=[USER])

    scripts = _values(items, 'startup-script')
    assert len(scripts) == 1
    assert 'echo image-custom-script' in scripts[0]
    assert 'sudo useradd -m -s /bin/bash "$USERNAME"' in scripts[0]
    # The account is created before the image script runs, so a long or exiting script cannot skip it.
    assert scripts[0].index('useradd') < scripts[0].index('image-custom-script')
    assert scripts[0].startswith('#!/bin/bash')


def test_linux_template_without_a_user_keeps_the_image_script_alone():
    items = _metadata('linux', startup_script=IMAGE_SCRIPT, ssh_keys=['agoge:ssh-ed25519 AAAA'])

    assert _values(items, 'startup-script') == [IMAGE_SCRIPT]
    assert _values(items, 'ssh-keys') == ['agoge:ssh-ed25519 AAAA']


def test_windows_template_is_unchanged():
    ps1 = 'Write-Host image-custom-script'
    items = _metadata('windows', startup_script=ps1, human_interaction=USER)

    # The user script stays under the sysprep key; the image script keeps its own startup-script item.
    assert _values(items, 'startup-script') == [ps1]
    sysprep = _values(items, MetadataKey.WINDOWS)
    assert len(sysprep) == 1
    assert 'New-LocalUser' in sysprep[0]
    assert 'image-custom-script' not in sysprep[0]
    assert len(items) == 2


def test_lab_and_template_managers_share_one_merge_helper():
    # V4 reuses the lab server helper; a divergent copy would reintroduce Working Note 21.
    assert ImageTemplateManager._merge_metadata_item.__func__ is LabServerManager._merge_metadata_item.__func__
