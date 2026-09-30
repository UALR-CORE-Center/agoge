# Labs that run their own virtual machines

Some labs ship their targets inside the lab server rather than beside it: a single Kali host that runs Metasploitable guests under libvirt, a vulnerable domain built from local qcow2 images, and so on. The guest hypervisor needs `/dev/kvm`, which Google exposes only when the instance is created with nested virtualization enabled.

Two failures are common, they look similar from the terminal, and they are independent. A lab can hit both at once.

## `/dev/kvm is missing`

```
FATAL: /dev/kvm is missing — this VM cannot run any target.
  The VM must be an N2 machine type created with --enable-nested-virtualization.
network labnet NOT defined
```

The server was built without `advanced_machine_features.enable_nested_virtualization`.

Set **Nested Virtualization** in the server's **Settings** section in the specification editor, or `"nested_virtualization": true` on the server in the specification JSON. Before this setting existed, the build path turned nested virtualization on only as a side effect of assigning `ip_aliases` to a NIC, so older specifications carry alias addresses they never use. That trigger still works and needs no migration.

Two constraints come with it:

- **The machine type must be `n1` or `n2`.** E2 machines cannot do this at all. A specification that pairs nested virtualization with an E2 is rejected when it is saved, and the build fails rather than producing a server that looks healthy and cannot start a target.
- **The flag is fixed at creation.** Changing the specification does not alter a server that already exists; the unit or workout has to be rebuilt.

`min_cpu_platform` is filled in automatically when the specification leaves it blank — `Intel Haswell` for `n1`, `Intel Cascade Lake` for `n2` — because N1 can otherwise land on a CPU generation that predates VMX exposure. An explicit value in the specification is left alone.

To confirm what a built server actually got:

```bash
gcloud compute instances describe <workout-id>-<server> --zone <zone> \
  --format="yaml(machineType,minCpuPlatform,advancedMachineFeatures)"
```

An instance with no `advancedMachineFeatures` block has nested virtualization off.

### Enabling it on a server that already exists

Rebuilding is the supported path. To repair a running workout in place instead, stop the instance, set the flag, and start it again. The external IP is ephemeral, so a stop/start assigns a new one and the DNS record in the parent project has to be updated to match — the platform does this itself only when it starts the server, so a manual `gcloud` start needs a manual record update.

## `libvirtd` fails with status 243/CREDENTIALS

This one is a property of the image, not of the instance, and it appears on every VM cloned from that image.

```
libvirtd.service: TPM key integrity check failed. Key most likely does not belong to this TPM.
libvirtd.service: Failed to set up credentials: Object is remote
libvirtd.service: Failed at step CREDENTIALS spawning /usr/sbin/libvirtd: Object is remote
```

`virsh` then reports `failed to connect to the hypervisor`, and the lab's own tooling reports the network as not defined, because no daemon is listening.

Debian's `libvirt-daemon-driver-secret` package generates `/var/lib/libvirt/secrets/secrets-encryption-key` on first boot through `virt-secret-init-encryption.service`, using `systemd-creds encrypt`. On a machine with a TPM — every Shielded VM has a vTPM — that seals the key to *that machine's* TPM. The unit is guarded by `ConditionPathExists=!` on the key file, so it runs exactly once.

Capturing an image after that point bakes in a key sealed to the build VM's vTPM. Every clone inherits the file, the condition skips regeneration, and `libvirtd` can never decrypt it.

### What Agoge does about it

Checking a Linux template server out installs a small unit, `libvirt-secret-key-heal.service`, whose job is to make this self-correcting. It is ordered ahead of `virt-secret-init-encryption.service` and `libvirtd.service`, and on each boot it tries to decrypt the existing key. A key it can decrypt is left alone; one it cannot is deleted, so the stock generator makes a new one sealed to the current TPM. It always exits 0, so it can never be the reason a lab server fails to boot, and it is guarded on libvirt's secret driver being installed, so it is inert on the images that never run a hypervisor in the guest.

This is installed at check-out rather than check-in because `create_production_image` stops the server before it snapshots — by check-in time nothing can run in the guest. See `ImageHygieneStartupScript`.

An image that predates this carries no such unit. Those need either a re-capture or the manual repair below.

### Preparing the image by hand

If you are building an image outside the check-out flow, delete the key before capturing, as part of the same pass that clears machine-specific state:

```bash
sudo rm -f /var/lib/libvirt/secrets/secrets-encryption-key
```

`virt-secret-init-encryption.service` then regenerates it on each new VM's first boot, sealed to that VM's own TPM.

A convenient way to do this without an interactive session is to boot a VM from the image with a startup script that removes the key and then runs `shutdown -h now`, and capture the image from that disk once the instance reports `TERMINATED`.

### Repairing a running server

Same removal, then restart the units. `libvirtd` will have hit its start limit after the boot-time retries, so clear that first:

```bash
sudo rm -f /var/lib/libvirt/secrets/secrets-encryption-key
sudo systemctl reset-failed libvirtd
sudo systemctl start virt-secret-init-encryption.service
sudo systemctl start libvirtd
```

Networks marked autostart come up with the daemon; check with `sudo virsh net-list --all`.

This is worth checking for in any image whose services use systemd's encrypted credentials, not just libvirt. `grep -rl 'LoadCredentialEncrypted\|SetCredentialEncrypted' /etc/systemd/system /usr/lib/systemd/system` lists the units that would be affected.
