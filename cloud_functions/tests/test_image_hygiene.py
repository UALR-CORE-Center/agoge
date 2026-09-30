"""Image hygiene installed on template servers at check-out.

libvirt generates /var/lib/libvirt/secrets/secrets-encryption-key with `systemd-creds encrypt`,
sealing it to the local TPM, and its generator unit is guarded by ConditionPathExists=! so it runs
exactly once. An image captured after that point carries a key sealed to the builder's vTPM; every
clone inherits it, skips regeneration, and libvirtd exits 243/CREDENTIALS -- which reads in the
guest as "failed to connect to the hypervisor" and leaves every network and domain undefined.

create_production_image() stops the server before snapshotting, so nothing can run in the guest at
check-in. The repair therefore has to be installed while the template server is checked out.
"""
from unittest.mock import MagicMock

from cloud_fn_utilities.course_objects.compute.image_template_manager import ImageTemplateManager
from cloud_fn_utilities.server_specific.agoge_user_startup_script import MetadataKey
from cloud_fn_utilities.server_specific.image_hygiene_startup_script import ImageHygieneStartupScript


def _manager(os_name):
    manager = object.__new__(ImageTemplateManager)
    manager.server_spec = MagicMock()
    manager.server_spec.os = os_name
    return manager


def _linux_script(interactions=None):
    manager = _manager('linux')
    result = manager._generate_startup_script(
        interactions if interactions is not None else [{'username': 'student', 'password': 'pw'}]
    )
    assert result is not False
    key, script = result
    assert key == MetadataKey.LINUX
    return script


def test_linux_checkout_script_installs_the_heal_unit():
    script = _linux_script()

    assert ImageHygieneStartupScript.HEAL_UNIT in script
    assert ImageHygieneStartupScript.HEAL_BIN in script
    assert f'systemctl enable {ImageHygieneStartupScript.HEAL_UNIT_NAME}' in script


def test_hygiene_is_guarded_on_libvirt_being_installed():
    """Most images never run a hypervisor in the guest; the fragment must be inert for them."""
    script = _linux_script()

    assert f'systemctl list-unit-files {ImageHygieneStartupScript.LIBVIRT_GENERATOR_UNIT}' in script


def test_heal_unit_is_ordered_before_the_generator():
    """Removing the key only helps if it happens before ConditionPathExists=! is evaluated."""
    unit = '\n'.join(ImageHygieneStartupScript._heal_unit_lines())

    assert f'Before={ImageHygieneStartupScript.LIBVIRT_GENERATOR_UNIT}' in unit
    assert 'Before=libvirtd.service' in unit
    # Without this the unit runs on every boot of every server, for nothing.
    assert f'ConditionPathExists={ImageHygieneStartupScript.LIBVIRT_SECRETS_KEY}' in unit


def test_heal_script_keeps_a_key_it_can_decrypt():
    """A correctly sealed key must be left alone, or every boot throws away working state."""
    body = '\n'.join(ImageHygieneStartupScript._heal_script_lines())

    assert 'systemd-creds decrypt --name=secrets-encryption-key' in body
    # The decrypt succeeding has to be an early return, ahead of the rm.
    assert body.index('exit 0') < body.index('rm -f')


def test_heal_script_never_fails_the_boot():
    body = '\n'.join(ImageHygieneStartupScript._heal_script_lines())

    assert body.rstrip().endswith('exit 0')


def test_hygiene_runs_after_the_connection_accounts_are_created():
    """Ordering matters: a broken hygiene block must not cost the instructor their login."""
    script = _linux_script([{'username': 'student', 'password': 'pw'}])

    assert script.index('useradd') < script.index(ImageHygieneStartupScript.HEAL_BIN)


def test_windows_checkout_script_is_untouched():
    manager = _manager('windows')

    key, script = manager._generate_startup_script([{'username': 'student', 'password': 'pw'}])

    assert key == MetadataKey.WINDOWS
    assert 'libvirt' not in script


def test_unknown_os_still_returns_false():
    manager = _manager('plan9')

    assert manager._generate_startup_script([{'username': 'student', 'password': 'pw'}]) is False
