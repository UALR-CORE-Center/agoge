# Agoge Instructor Guide

Agoge lets instructors publish reusable lab templates, create course lab deployments, and monitor each learner's environment.

> **Agoge terminology**
>
> - A **lab template** is the reusable definition in the Lab Catalog.
> - A **Lab** is an instructor-created course assignment with an expiration date and roster or join code.
> - A **Workout** is one learner's environment within that Lab. Some current buttons and status messages use the word Workout.

## Before you begin

You need an Agoge account with instructor permission. Your deployment administrator must also have configured any LMS connection, reusable server images, and sufficient Google Cloud quota for the number of concurrent learner environments you plan to run.

Choose expiration dates and capacities conservatively. Allow time for late work, but avoid leaving unused resources available longer than necessary.

## Quick navigation

| Task | Current interface path |
| --- | --- |
| View active or expired Labs | **Teachers → Manage Labs** |
| Build a Lab from a template | **Teachers → New Lab** |
| Create or edit a template | **Teachers → New Lab → Create New Template** |
| Manage reusable server images | **Teachers → Manage Servers** |
| Configure your LMS connection | Account menu → **Settings** |

## Build a Lab from the catalog

1. Open **Teachers → New Lab**. The page heading is **Lab Catalog**.
2. Review the available templates. Use **View Details** or **Instructions** when those actions are available.
3. Select one template row, then click **Build Lab**.
4. Set **Expires** to the final date and time learners should have access. Include any planned late-work window.
5. For a join-code Lab, set **Max number of students** from 1 to 100. This is the maximum number of learner Workouts that can be claimed, not merely an expected enrollment.
6. If the Lab is connected to an LMS, enable **Build with LMS**, select the configured provider, and choose the **Course Code**.
7. Confirm with **Build Workout!**. This is the build dialog's current button label.
8. Wait for Agoge to open the Lab detail page. The page contains the Lab summary, expiration controls, distribution information, and **Student Lab Workouts** table.

A join-code build creates the Lab record first. Agoge provisions an individual Workout when each learner claims the Lab. An LMS build uses the course roster; select the required learner rows in **Student Lab Workouts** and click **Build** when their Workouts need to be provisioned.

### LMS notes

Only use an LMS provider that your deployment administrator has configured and tested. The current backend supports Canvas and Google Classroom workflows. Blackboard may appear in some interface lists but is not supported by the current unit-build backend unless your deployment includes a compatible extension.

For Canvas, configure the **API Key (Canvas)** and **URL (Canvas)** under **Settings** before building the Lab. LMS-specific setup varies by institution, so do not include credentials in lab instructions or repository files.

## Distribute a join-code Lab

The Lab detail card displays the learner claim URL, **Join Code**, **Copy Join Code**, and current **Capacity**.

Share all three of the following with learners:

1. The claim URL shown by Agoge.
2. The join code.
3. The [Agoge Learner Guide](learner-guide.md).

Ask learners to enter a valid email address consistently. Agoge uses that address to find the same Workout on a later visit, and the address is visible to the instructor. If your course requires a particular address, such as the LMS or institutional email, state that explicitly.

As learners claim the Lab, they appear in **Student Lab Workouts**. A learner who submits the same join code and normalized email again is returned to the existing Workout rather than consuming another seat.

## Monitor and manage a Lab

Open **Teachers → Manage Labs**. The page has **Active Labs** and **Expired Labs** tabs under **Your Labs**. Select a Lab by clicking its ID.

The Lab detail page provides these controls:

| Control | Purpose |
| --- | --- |
| **Extend By (days)** and **Extend Expiration** | Extend an active Lab before it expires |
| **View Workout** | Open the learner-facing environment for inspection |
| **Build** | Provision selected LMS roster Workouts |
| **Start** | Start the selected learner Workouts |
| **Stop** | Stop the selected Workouts while retaining normal disk state |
| **Rebuild Workout** | Recreate one learner environment; use only after confirming that replaceable learner work will not be lost |
| **Snapshot** | Snapshot all servers in the selected Workouts |
| **Manage Workout Snapshots** | Open the per-server Snapshot Manager for one Workout |
| **Assessment** | Review the selected learner's assessment responses |

Most table actions require selecting one or more learner rows first. Stopping unused Workouts reduces metered compute use; it does not change the Lab's expiration date.

Expired Labs remain listed under **Expired Labs**, and their recorded assessment data may still be reviewed. Build, start, stop, rebuild, snapshot, and extension actions are disabled after expiration, so extend access before the displayed deadline.

## Create a new lab template

Open **Teachers → New Lab**, then click **Create New Template**. You can also start from an existing template with **Create Copy of Specification**.

The editor saves each valid step as you move forward. It uses this sequence:

| Step | What to configure |
| --- | --- |
| **Lab Summary** | Name, Author, Unit Type, teacher and student instructions, Description, and optional Teaching Concepts |
| **Networks** | Network name, private IPv4 range in CIDR notation, and Promiscuous Mode when traffic monitoring is required |
| **Servers** | Reusable Server Image, machine type, disk size, network interface, addressing, visibility, sharing, and outbound-traffic settings |
| **Web Applications** | Optional application Name, Host Name, and Starting Directory |
| **Assessment** | Optional questions and automated assessment script configuration |
| **Review** | Validate the complete template, return to any flagged section, and publish it |

### Choose the Unit Type

- **Solo** creates an isolated Workout for each learner.
- **Community** places learner Workouts in a shared network environment and can include shared community servers.

Use Community only when learners are intentionally expected to interact across the shared environment.

### Configure networks

The editor begins with an **external** network. Enter a valid private IPv4 range in CIDR notation. Enable **Promiscuous Mode** only when a server must observe network traffic for an exercise.

At least one saved network is required before you can configure servers.

### Configure servers

Add each server and select its reusable **Server Image**. Configure its machine type, disk size, and network interface. Available interface and server settings include:

- **Hide Server** to omit a server from the learner's server list.
- **Community Server** to share the server in a Community Lab.
- **Deny Outbound** to block traffic initiated from the server while retaining permitted local-network traffic.
- **Enable External NAT** when the exercise requires outbound internet access.
- **Enable Direct Connections** when learners should connect directly to the server.

Connection credentials and protocols are part of the reusable server image's **Human Interaction** configuration under **Manage Servers**; they are not selected in this template step. The standard connection dialog presents RDP and SSH details, so verify any deployment-specific protocol extension before assigning it to learners.

### Configure web applications and assessments

Use **Add Web Application** to define an application by Name, Host Name, and optional Starting Directory. Agoge presents these as buttons on the learner page.

Assessments are optional. Add clear questions and, when needed, an assessment script and its install server. Verify exact-answer questions carefully because learners submit responses one question at a time.

### Review and publish

On **Review**, inspect every section and use the section links to fix validation errors. Click **Publish** when the template is ready.

There is no separate Test action. The safest validation is to build a short-lived, one-participant, non-LMS Lab from the published template, claim it with a test email, and verify:

- Provisioning completes.
- Instructions open.
- Expected servers and web applications appear.
- Direct and Guacamole connections work.
- Network restrictions behave as intended.
- Assessment answers evaluate correctly.
- Stop, start, snapshot, and restore work as expected.

## Create and edit Markdown instructions

Agoge supports separate instructor and learner instruction documents.

1. In **Lab Summary**, locate **Teacher Instructions** or **Student Instructions**.
2. Select an existing document, or use **Create New Teacher File** or **Create New Student File**.
3. Enter a **File Name** and click **Create**. The Markdown editor opens in a new tab.
4. Write the instructions and click **Save**.
5. Return to the template editor and confirm that the intended document is selected.
6. Use the pencil action to reopen an existing instruction document for editing.

Teacher instructions appear on the instructor's Lab detail page. Student instructions appear behind the learner's **Instructions** button.

Effective learner instructions normally include prerequisites, objectives, expected time, connection target, ordered tasks, required evidence, assessment expectations, and cleanup. Never include permanent credentials or sensitive institutional data.

## Manage reusable server images

Reusable server images provide the operating system, applications, data, and connection configuration used by lab templates.

### Modify an existing image

1. Open **Teachers → Manage Servers**.
2. For a checked-in image, choose **Check Out Template Server**. Wait for the modifiable server to be prepared.
3. Click **Start Template Server** and wait for the state to become **Running**.
4. Click **Connect** and use the configured connection method.
5. Make and verify the required changes inside the server.
6. Stop the server when it is idle.
7. Choose **Check In Template Server** to create or update the reusable image. Check-in may take several minutes.
8. Build a pilot Lab using the updated image.

Use **Cancel Template Server Changes** to discard a checkout. Do not cancel or check in until you have saved any files you intend to retain.

The image's edit action manages metadata and **Human Interaction** settings, including protocol and credentials. If you edit an image while it is checked out, those changes are not reflected in the reusable image until check-in completes.

### Create a new image

Click **Create Image**, select an existing project or global base image, and provide the server name, disk size, description, labels, authorization settings, and display support as required. After creation completes, use the normal checkout, start, connect, verify, and check-in workflow.

Checked-out or running template servers incur cloud cost. Stop them when not in use and check them in promptly after validation.

### If base images are missing from the creation page

The **Machine Configuration → Server Image** selector combines public OS images with custom Agoge images. Each catalog can be used independently, so a new project can create its first custom server from a public Ubuntu, Debian, or Windows image.

1. Expand **Server Image** and choose **Clear Filter** to remove any project filter.
2. If public images are still missing, ask a project administrator to open **Admin → Image Manager** in the same Agoge site. Choose **Sync**, allow a few minutes for the background task, then choose **Refresh**.
3. Confirm that the desired public image is marked **Enabled**. Select it and choose **Enable** if needed, then **Refresh** to confirm. Disabled public images are excluded from the creation selector.
4. Reload the server creation page and select the base image.

The public catalog is synchronized into each child project's database. A shared image project setting does not populate this catalog. If **Sync** fails or the catalog stays empty, the administrator should check the child's Cloud Function logs for `GoogleImageSyncManager` and confirm that its Agoge Pub/Sub function is processing requests. Custom images also need an Agoge image record; creating an image directly in the GCP console alone does not add it to this selector.

An administrator can also select the child project in `python setup.py` and run **Server Images & Build Specs → Synchronize Public OS Images**. This populates the catalog directly and prints errors in the terminal, without waiting for the background function. Full installations run it automatically. See [public OS catalog setup and recovery](../operations/shared-project-setup.md#public-os-image-catalog). New Ubuntu, Debian, and Windows families are enabled by default; other public families require **Enable** in Image Manager. The selector lists available image families, not every historical version.

### If a new server reports no bootable device

Check CPU architecture first. The server creation form currently offers E2
machines, which require **AMD64 (x86-64)** images. An **ARM64** Ubuntu image
cannot boot on an E2 machine even if its disk includes `UEFI_COMPATIBLE`.
For example, `ubuntu-minimal-2204-jammy-arm64-v20260906` is an ARM image.
For the WireGuard template, choose **Ubuntu 24.04 LTS AMD64**, family
`ubuntu-2404-lts-amd64`, from `ubuntu-os-cloud`. See Google's
[E2 machine details](https://docs.cloud.google.com/compute/docs/general-purpose-machines#e2_machine_series)
and [Ubuntu image families](https://docs.cloud.google.com/compute/docs/images/os-details#ubuntu).

The selector displays CPU architecture and disables ARM64 selections for this
form. The API validates the actual source image and machine architecture before
saving or queuing a new server. The Cloud Function checks again before building
a template, including existing records and queued requests. Missing architecture
metadata stops the build with an explanation instead of assuming compatibility.
Public catalog synchronization fills the architecture field for older records.

GCP's **RUNNING** state means the VM is powered on, not that its operating system has started. Serial messages such as `Boot failed: not a bootable disk` or `No bootable device` indicate failure before SSH or the account setup script can run. Changing the SSH key will not resolve that boot failure.

Ask an administrator to inspect the attached boot disk and serial output. These PowerShell examples use the `wireguard-server` template in `test-dev-787001`:

```powershell
gcloud compute instances describe wireguard-server --project=test-dev-787001 --zone=us-central1-a --format="yaml(name,status,disks)"
gcloud compute disks describe wireguard-server-disk --project=test-dev-787001 --zone=us-central1-a --format="yaml(name,creationTimestamp,sourceImage,sourceImageId,sourceSnapshot,sourceSnapshotId,guestOsFeatures,architecture,sizeGb,users)"
gcloud compute instances get-serial-port-output wireguard-server --project=test-dev-787001 --zone=us-central1-a --port=1 | Select-Object -Last 120
```

Use the disk name shown for `boot: true` if it differs from `wireguard-server-disk`. Compare its source with the image selected in Agoge. A missing `sourceImage` alone does not prove the disk was created empty; Google omits that field if the source image was subsequently deleted. Check the source ID and other disk metadata too. See [Google's disk resource reference](https://docs.cloud.google.com/compute/docs/reference/rest/v1/disks).

Agoge now retains the selected base image through the first checkout and switches to the custom image only after check-in. Boot creation also rejects an orphaned or incompatible disk with the expected name instead of allowing it to be silently reused. Google documents that an existing disk matching `initializeParams.diskName` can be attached instead of creating a new disk; this is a possible cause to investigate, not a diagnosis from the serial message alone. See [the instance creation reference](https://docs.cloud.google.com/compute/docs/reference/rest/v1/instances/insert).

To recover after pulling these fixes:

1. Have the administrator deploy the updated **React application, API, and Cloud Function** to the affected child project. Run **Server Images & Build Specs → Synchronize Public OS Images** in setup to refresh architecture metadata in the public catalog.
2. Create a replacement template with a **new server name**, such as `wireguard-server-v2`, and select the intended Ubuntu **AMD64** image for an `e2` VM. A new name avoids reusing the failed disk.
3. Confirm Ubuntu boots and SSH works before configuring and checking in the replacement.
4. Retain the failed VM and disk for inspection. Restarting does not recreate or repair the disk, and the new safeguard does not delete it automatically. Stop the failed VM while it is not being inspected.

If the disk is ARM64 and the VM is E2, recovery requires a fresh AMD64 image
and disk. Increasing disk size, changing SSH keys, or toggling Secure Boot
does not convert an ARM operating system into an x86 operating system.

## Create, restore, and delete snapshots

Snapshots preserve server disk state before risky changes. They are useful recovery points, but they are not a substitute for exporting important learner work.

### Snapshot selected learner Workouts

1. Open the Lab and select one or more rows in **Student Lab Workouts**.
2. Click **Snapshot**.
3. Wait for the request to finish. Agoge snapshots the servers in each selected Workout.

### Manage snapshots for one Workout

1. Open the row action **Manage Workout Snapshots**.
2. Select the tab for the server you want to manage.
3. Click **Snapshot** to create a new snapshot.
4. To restore, select one snapshot row and click **Restore**.
5. To remove an unneeded snapshot, select it and click **Delete**.

Snapshot, restore, and delete requests can take up to several minutes. A restore replaces the server's current disk state with the selected snapshot. Coordinate with the learner, save needed work, and stop active work before restoring.

Template server snapshots are available from **Manage Servers** while the image is checked out and use the same per-server Snapshot Manager.

## Troubleshooting

| Problem | Checks |
| --- | --- |
| Learner receives an invalid join-code message | Confirm the copied code, verify the Lab is active, and have the learner remove accidental spaces |
| Learner cannot claim a seat | Check **Capacity** and the configured maximum; confirm that the email has not already been entered differently |
| Workout stays in a build state | Allow 5–10 minutes for normal provisioning, then refresh and inspect the state |
| Workout is **Broken** | Review available status details; use Rebuild only after confirming the learner's replaceable work, or contact the deployment administrator |
| **Connect** is disabled | The Workout must be **Running**, and direct access may still be configuring for the learner's current public IP |
| Direct RDP or SSH fails | Ask the learner to refresh after a Wi-Fi, VPN, or hotspot change; verify **Access Configuration** and try Guacamole |
| Lab is already **Expired** | Normal instructor controls cannot extend it after expiration; contact the deployment administrator if recovery is required |
| New builds exceed cloud limits | Reduce concurrent Workouts, stop unused resources, and ask the administrator to review project quotas |
