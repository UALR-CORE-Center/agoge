# Nested Lab Host Guide

A **nested lab host** is an Agoge image whose server is a hypervisor. It is a Debian **parent** VM that runs libvirt/QEMU-KVM and up to eight **guest** VMs (Kali, Linux distributions, Windows, network appliances) on networks you define inside the parent. One lab server built from the image carries a whole small network.

You build one from the Create Image page. Agoge provisions the parent, installs every guest, and leaves the host checked out so you can customize it. **Check In** then shuts the guests down cleanly and saves the image. The finished image appears in the server picker of the lab spec editor and of CTF templates, like any other image.

This guide assumes you already know how to manage images and Labs. If you don't, read the [Instructor Guide](instructor-guide.md) first. For flags on guests, see [Nested lab hosts](game-master-guide.md#nested-lab-hosts) in the Game Master Guide.

## Before you begin

- A deployment administrator must run `setup.py` option **Configure Nested Image Media Bucket** once. It creates the `<project>_nested-media` bucket that holds your uploads and caches downloaded media.
- The guest operating systems you can choose come from the `nested-os-catalog` collection, which the administrator maintains. Each entry names its install method, where its media comes from, and a license note. An entry whose download has no published SHA-256 cannot be downloaded: the build fails that guest with "the catalog entry has no media_sha256, so its download cannot be verified". Ask the administrator to add the hash, or upload the media yourself.

## Licensing

Read the license note the OS picker shows before you add a guest. You are responsible for licensing every guest you install.

- **Agoge downloads only media its publisher hosts publicly**, and verifies each download against the catalog's SHA-256.
- **Agoge never downloads or redistributes Windows media** beyond what Microsoft publishes. Retail, volume, and legacy Windows (XP, Server 2003, Vista, 7, 8.1, Server 2008–2012 R2, and licensed 2016–2025) require an **upload** of media you are licensed to use.
- **Evaluation editions expire.** Windows Server 2016–2025 Evaluation runs 180 days, and Windows 11 Enterprise Evaluation runs 90 days. Microsoft no longer offers a Windows 10 Enterprise evaluation, so Windows 10 needs uploaded media and a product key. The clock starts at install time, so it is already running in every lab built from the image. To extend it, run `slmgr /rearm` in the guest (as administrator, then reboot) and Check In again. Rearms are limited, so plan to rebuild the image before the last one runs out.
- **Product keys** are entered on the guest in the wizard, used once for the unattended install, and never stored. Windows entries that are not evaluations require one.
- **Upload requirements:** one file per upload, at most 20 GiB, in a format the catalog entry accepts (the **Media** list shows only completed uploads that fit the chosen OS). Accepted formats include `iso`, `qcow2`, `raw`, `vmdk`, `vhd`, `vhdx`, `ova`, `zip`, `7z`, `img.xz`, `img.bz2`, `iso.gz`, and `tar.xz`. The upload link is valid for one hour, and an upload that never finishes is deleted after two days. Agoge does not verify uploads against a hash; upload only media you obtained from a source you trust.

## Sizing

The wizard checks these limits before it lets you create the image:

| Resource | Rule |
| --- | --- |
| Machine type | **Build machine type** and **Lab machine type** must be N1 or N2 (nested-capable). E2 is not offered. Types up to 64 GB of memory are listed. |
| Memory | The guests' memory plus 2048 MB for the parent must fit in both machine types. |
| vCPUs | The guests' vCPUs may total at most twice the machine's vCPUs. |
| Disk | At least 20 GB for the parent, plus every guest's disk, plus 12 GB of build scratch space, plus the size of each installation medium (cloud image, ISO, or upload), rounded up to whole GB. Media stay on the parent until the build finishes, and guests that share one medium count it once. At most 1000 GB. Leave it empty to use this minimum; you can raise it. |
| Guests | 1 to 8, each with 1 to 4 NICs. |
| Exposed NICs | At most 8. |

Build on a bigger machine than the lab needs: the default **Build machine type** is `n2-standard-8`, and Windows installs much faster with more cores. The **Lab machine type** is what lab servers built from the image use by default.

## The wizard

On the Create Image page, set the image type to **Nested lab host**. The wizard has five steps, which you can visit in any order. **Create image** on the last step is enabled only when every step is valid; a step with an error says so in its tooltip.

### Host

- **Server Name**: the image is saved as `image-<name>`. Up to 54 lowercase letters, numbers, or hyphens. `nested` is reserved.
- **Description** and **Image Labels**.
- **Parent OS**: Debian 12 or 13.
- **Build machine type**, **Lab machine type**, and **Disk Size (GB)**: see [Sizing](#sizing).
- **Username** and **SSH Public Key**: your login on the parent, used for the tunnels described below.

### Networks

Each network is a libvirt network inside the parent. Add up to eight with **Add network**; the **Topology** diagram shows the result.

| Field | Rules |
| --- | --- |
| **Name** | 2 to 15 lowercase letters, digits, or `-`. Unique. |
| **CIDR** | A private range from /16 to /29. It may not overlap another network, `169.254.0.0/16`, or `192.168.122.0/24`. |
| **Mode** | **NAT** gives guests internet access through the parent. **Isolated** has no route out. |
| **Parent address** | The parent's own address on the network. Required for NAT and for DHCP. Leave it empty for a pure layer-2 segment the parent cannot reach. |
| **DHCP**, **DHCP start**, **DHCP end** | The range must exclude the parent address and every static guest IP. |

### Guests

**Add guest** opens **Choose an operating system**. The chips show whether an entry installs automatically (**Auto install**) or in the console (**Manual install**), whether it needs an **Upload**, its evaluation period, and **No agent** for guests without the QEMU guest agent.

For each guest:

- **Name**: 2 to 15 lowercase letters, digits, or `-`. It is the guest's hostname, its libvirt domain name, and its Windows computer name.
- **Memory (MB)** and **Disk (GB)**: at least the catalog entry's minimum.
- **Admin username** and **Admin password**: the account the install creates. The password is stored with the image, and instructors can see it. Windows passwords need at least 8 characters from 3 of the 4 character classes.
- **Product key**: see [Licensing](#licensing).
- **Installation media**: for entries that need an upload, pick a completed upload from **Media** or use **Upload**.
- NICs (**Add NIC**): choose a **Network**, then **DHCP** or **Static** addressing. **Expose** makes the NIC reachable from the lab VPC through an alias IP on the lab server, and requires a static IP.
- **Packages**: extra packages, for cloud-image Linux guests only.
- **Post-install script**: bash for Linux, PowerShell for Windows. It runs once through the guest agent after the install, so guests marked **No agent** never run it. A non-zero exit fails the guest.
- **VNC console**, **Autostart**, **Start order**, and **Start delay (s)**: these control how the guest is reached and started. Guests start in **Start order** at every boot of the parent.

Install methods:

| Method | What happens |
| --- | --- |
| Cloud image (Linux, Kali) | The image is customized offline with your user, password, the guest agent, SSH, your packages, and the network settings, then imported. |
| Unattended ISO (Windows) | Windows Setup runs from a generated answer file. It installs the virtio guest tools where the catalog has them, enables RDP and ping, sets static IPs, deletes the answer file (it holds the password), and powers off. The builder then removes the install media and starts the guest. |
| Disk image | An uploaded or downloaded disk is unpacked and converted. Linux disks with an agent get the same user and agent setup as a cloud image. |
| Manual install | A blank disk boots the ISO with the console on. The guest stays at status **Manual install** until you finish the install yourself in the console. |

### Access

**Exposed NICs** lists every exposed NIC in alias-slot order; use the arrows to reorder them. Slot *i* is reached through the lab server's *i*-th alias IP on NIC 0, so the order matters when you build a lab from the image. **Consoles** lists each guest's VNC console port, starting at 5901.

### Review

Review shows the host, capacity, credentials (**Show passwords** reveals them), the estimated build time, and warnings: evaluation periods and `slmgr /rearm`, manual installs to finish before Check In, guests without an agent, Windows media that Agoge never redistributes, and the 240-minute build limit.

## Build time and progress

After **Create image**, the server list shows the image with a **Nested build** chip: **Queued**, **Provisioning**, **Building guests**, then **Guests ready** (or **Build failed**). Hover over the chip for the builder's latest message, and open **View Details** for each guest's status: Pending, Downloading, Installing, Post-install, Manual install, Ready, or Failed.

Linux cloud-image guests typically take a few minutes each. A Windows Server install took under 10 minutes on `n2-standard-8`. Downloads of large ISOs often take longer than the install. The builder installs at most two guests at a time.

One failed guest does not stop the others. The build ends **Guests ready** when at least one guest is ready or waiting for a manual install, and the message names the guests that failed. It ends **Build failed** only when no guest made it. Agoge stops a build that reports no progress for 45 minutes, or that runs longer than 240 minutes, and stops the server. The guests' passwords are removed from the server's metadata as soon as the build finishes, whether it succeeded or not.

**Check In** is disabled while the build is queued, provisioning, building, or finalizing.

### Troubleshooting a build

SSH to the parent with the username and key from the Host step (the **Connect** column shows its address), then:

| Where | What |
| --- | --- |
| `/var/log/agoge-nested-builder.log` or `journalctl -u agoge-nested-builder` | The builder's full log. |
| Guest attribute `agoge-nested/message` | The latest step, which is also the chip's tooltip. Read it with `gcloud compute instances get-guest-attributes <server> --query-path=agoge-nested/`. |
| `agoge-nested/guest-<name>` | Each guest's status, with `failed:<reason>` on failure. |
| `/var/lib/agoge-nested/state/` | Per-step markers. A reboot resumes the build instead of restarting it. |
| `journalctl -u agoge-nested-runtime` | Alias-to-guest mapping and firewall setup at boot. |
| `virsh list --all`, `virsh console <guest>` | The guests themselves. |

Common failures:

| Message | Fix |
| --- | --- |
| "media sha256 mismatch: expected …, got …" | The publisher changed the file. Ask the administrator to update the catalog entry. |
| "could not download the media" / "could not download the uploaded media" | The URL moved, or the upload was deleted. Check the catalog entry, or upload again. |
| "the catalog entry has no media_sha256, …" | See [Before you begin](#before-you-begin). |
| "virt-customize failed: …" | The cloud image could not be customized, usually because of a package name in **Packages**. |
| "agoge-nested-secrets is missing; the build cannot continue" | The server restarted after the build's passwords were removed. Delete the image and create it again. |
| "The build stopped reporting progress for 45 minutes and was stopped." | Read the builder log for the last step. A Windows install waiting on a prompt usually means a missing or wrong product key. |

To retry, delete the image and create it again with the same settings. Media you uploaded stays available.

## Customize through tunnels

Guests have no public address. You reach them through an SSH tunnel to the parent. The **Connect** dialog's **Nested guests** section lists ready-made commands, and **View Details** lists each guest's credentials and VNC password.

- **Console**: `ssh -L 5901:localhost:5901 <user>@<host>`, then point a VNC viewer at `localhost:5901` and enter the guest's VNC password.
- **Exposed Windows guest**: `ssh -L <local port>:<guest ip>:3389 <user>@<host>`, then RDP to `localhost:<local port>`. The dialog uses 13389 plus the alias slot.
- **Exposed Linux guest**: `ssh -L <local port>:<guest ip>:22 <user>@<host>`, then `ssh -p <local port> <admin>@localhost`. The dialog uses 2222 plus the alias slot.

The local ports in the dialog differ by alias slot, so you can keep several tunnels open at once. Finish any **Manual install** guests in the console now. Install the lab software, create the users, and plant whatever the exercise needs.

Like any checked-out image server, the parent is stopped at midnight by daily maintenance. Starting it again starts the guests in their start order.

## Finalize

Click **Check In** (the Check In Template Server button) when the guests are ready. For a nested image, Check In first **finalizes** the host:

1. Every running guest gets an ACPI shutdown and has 4 minutes to power off. Agoge never forces a guest off.
2. Each guest's `agoge-pristine` snapshot is (re)created. CTF guest **Rebuild** reverts to it.
3. Install media, build files, and the apt cache are deleted, and the disk is trimmed.
4. The ordinary check-in then images the disk, adding the `enable-vmx` license. The phase becomes **Finalized**.

If finalize fails, the image stays checked out and you can Check In again:

| Message | Fix |
| --- | --- |
| "&lt;guest&gt;: guest did not shut down" | The guest ignored the ACPI shutdown (on Windows, check the power-button setting, and that no one is signed in with unsaved work). Shut it down in the console, then Check In again. |
| "&lt;guest&gt;: could not create the agoge-pristine snapshot" | Internal snapshots need a qcow2 disk and do not work for UEFI guests. Check `/var/log/agoge-nested-finalize.log`. |
| "The host did not answer the finalize within 360 seconds. Check In again to retry." | The parent was stopped or busy. Start it, wait for the guests, and Check In again. |

To change a finalized image, **Check Out** again. Nothing is rebuilt: you get the guests as you left them. Check In finalizes again.

## Use the image in a lab

In the lab spec editor, choose the image for a server. Its NIC 0 needs one **alias IP per exposed NIC**: alias slot *i* is the *i*-th exposed NIC from the Access step. The server's machine type must be N1 or N2 (E2 types are hidden for nested images).

When you select a nested image, the server form shows a **Nested guests** panel:

- **Fill alias IPs** picks free addresses in NIC 0's subnet, in slot order, and keeps valid aliases already there.
- **Add connections** adds Guacamole connections: RDP for each exposed Windows guest, SSH for each exposed Linux guest (both to the guest's alias IP), and a VNC console for each other guest with a console. The parent's own connections are kept.

At every boot, the lab server maps each alias IP to its guest (one-to-one NAT), starts the guests in order, and blocks guests from reaching the parent itself or the metadata server. A missing alias leaves that guest unexposed; it does not fail the build. Stopping a workout shuts the guests down cleanly.

## CTF use

A nested image's server is a valid parent for `ctf.nested_guests` without `ip_aliases` of its own. In the CTF step of the spec editor, **Add guests from images (n)** adds each guest of the selected images: `domain` is the guest name, and `driver` is `qemu-agent` when the guest has the agent, otherwise `offline`. Add flags with **Guest** set as described in [Nested lab hosts](game-master-guide.md#nested-lab-hosts). The `agoge-pristine` snapshot that finalize creates is what a guest **Rebuild** reverts to.

## Security warning

**Root on the parent exposes every guest.** A user with root on the parent can open any guest's console, read or change any guest's disk, and read every flag the parent relays. The guests' admin passwords are also stored with the image and are visible to instructors. Do not give learners or teams a path to root on the parent unless controlling every guest is the intended reward, and do not reuse guest passwords anywhere else.
