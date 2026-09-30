from typing import List


class ImageHygieneStartupScript:
    """Startup-script fragments that keep a captured image safe to clone.

    A template server is a real VM, so some of the state it accumulates belongs to *that machine*
    and must not survive into an image. The clearest example is systemd's encrypted credentials:
    they are sealed to the local TPM, and every Shielded VM gets its own vTPM, so a credential
    generated on the template server cannot be decrypted by anything built from the resulting
    image.

    An image cannot be cleaned at check-in -- `create_production_image` stops the server before it
    snapshots, so nothing can run in the guest by then. The hygiene therefore has to be installed
    while the template server is checked out, which is what this fragment does. It is appended to
    the check-out startup script, runs on every boot of the template server, and is idempotent, so
    the effect is simply present in whatever image the instructor eventually checks in.
    """

    # Debian's libvirt-daemon-driver-secret generates this with `systemd-creds encrypt`, which
    # seals it to the local TPM. Its generator unit is guarded by ConditionPathExists=! on the
    # file, so it runs exactly once and never reconsiders.
    LIBVIRT_SECRETS_KEY = '/var/lib/libvirt/secrets/secrets-encryption-key'
    HEAL_BIN = '/usr/local/sbin/libvirt-secret-key-heal'
    HEAL_UNIT = '/etc/systemd/system/libvirt-secret-key-heal.service'
    HEAL_UNIT_NAME = 'libvirt-secret-key-heal.service'
    LIBVIRT_GENERATOR_UNIT = 'virt-secret-init-encryption.service'

    @classmethod
    def get_unix_script(cls) -> List[str]:
        """Returns the hygiene fragment for a Linux template server.

        Guarded on libvirt's secret-driver generator being present, so this is inert on the
        overwhelming majority of images, which never run a hypervisor inside the guest.
        """
        return [
            '',
            '# --- Agoge image hygiene: keep this image cloneable -------------------------------',
            '# libvirt seals its secrets key to the local TPM. Captured into an image, that key',
            '# cannot be decrypted by any VM built from it, so libvirtd fails to start with status',
            '# 243/CREDENTIALS -- which shows up in the guest as "failed to connect to the',
            '# hypervisor" and leaves every libvirt network and domain undefined. Install a unit',
            '# that discards an unusable key early in boot so the stock generator makes a new one.',
            f'if systemctl list-unit-files {cls.LIBVIRT_GENERATOR_UNIT} >/dev/null 2>&1; then',
            f'  sudo tee {cls.HEAL_BIN} >/dev/null <<\'AGOGE_HEAL_BIN\'',
            *cls._heal_script_lines(),
            'AGOGE_HEAL_BIN',
            f'  sudo chmod 0755 {cls.HEAL_BIN}',
            f'  sudo tee {cls.HEAL_UNIT} >/dev/null <<\'AGOGE_HEAL_UNIT\'',
            *cls._heal_unit_lines(),
            'AGOGE_HEAL_UNIT',
            '  sudo systemctl daemon-reload',
            f'  sudo systemctl enable {cls.HEAL_UNIT_NAME}',
            'fi',
            '# --- end Agoge image hygiene ------------------------------------------------------',
        ]

    @classmethod
    def _heal_script_lines(cls) -> List[str]:
        return [
            '#!/bin/sh',
            '# Discard a libvirt secrets key that this machine cannot decrypt.',
            '#',
            '# Installed by Agoge at image check-out. An image captured after libvirt generated',
            "# its key carries one sealed to the builder VM's vTPM; every clone inherits the file,",
            "# the generator's ConditionPathExists=! skips regeneration, and libvirtd exits",
            '# 243/CREDENTIALS. Removing the key lets the stock unit generate a usable one.',
            '#',
            '# Always exits 0. This must never be the reason a lab server fails to boot.',
            f'KEY={cls.LIBVIRT_SECRETS_KEY}',
            '',
            '[ -e "$KEY" ] || exit 0',
            '',
            'if systemd-creds decrypt --name=secrets-encryption-key "$KEY" - >/dev/null 2>&1; then',
            '    exit 0',
            'fi',
            '',
            'echo "libvirt secrets key cannot be decrypted on this machine; discarding it so that"',
            'echo "virt-secret-init-encryption.service regenerates one sealed to this TPM."',
            'rm -f "$KEY"',
            'exit 0',
        ]

    @classmethod
    def _heal_unit_lines(cls) -> List[str]:
        return [
            '[Unit]',
            'Description=Discard a libvirt secrets key that this machine cannot decrypt',
            '# Ordered ahead of the generator so that its ConditionPathExists=! is re-evaluated',
            '# after an unusable key has been removed.',
            f'Before={cls.LIBVIRT_GENERATOR_UNIT}',
            'Before=virtsecretd.service',
            'Before=libvirtd.service',
            f'ConditionPathExists={cls.LIBVIRT_SECRETS_KEY}',
            '',
            '[Service]',
            'Type=oneshot',
            f'ExecStart={cls.HEAL_BIN}',
            'StandardOutput=journal',
            'StandardError=journal',
            '',
            '[Install]',
            'WantedBy=multi-user.target',
        ]
