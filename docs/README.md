# Agoge Documentation

Agoge documentation is organized by audience and shipped with the web application.
Use the application's **Help** link to browse and search these Markdown guides.
These pages describe the interface and workflows in the matching deployed revision.

## User guides

| Audience | Guide | Covers |
| --- | --- | --- |
| Instructors | [Instructor Guide](guides/instructor-guide.md) | Building and distributing labs, creating templates, managing learner workouts, reusable server images, and snapshots |
| Game masters | [Game Master Guide](guides/game-master-guide.md) | Authoring a lab's `ctf` block, running a CTF event from create to archive, host reset modes, flag plant statuses, and the overnight-stop exemption |
| Learners | [Learner Guide](guides/learner-guide.md) | Claiming a lab, starting servers, connecting with RDP, SSH, or Guacamole, managing session time, and completing assessments |

## Project documentation

- [Register existing GCP server images](operations/import-server-images.md)
- [Optional rubric support and troubleshooting](troubleshooting/rubric-generation.md)
- [Project overview and deployment](../README.md)
- [Shared project setup and API secrets](operations/shared-project-setup.md)
- [Firebase authentication setup and troubleshooting](operations/firebase-authentication.md)
- [Community WireGuard example](examples/community-wireguard.md)
- [Managed WireGuard factory labs and deployment](operations/wireguard-provisioning.md)
- [Debug API and Cloud Function builds locally](operations/local-backend-debugging.md)
- [Validate community and solo behavior before deployment](operations/local-backend-debugging.md#validate-community-and-solo-behavior-without-gcp)
- [Troubleshoot Cloud Run deployment and startup](operations/cloud-run-deployment-troubleshooting.md)
- [Build and deploy the Markdown help app](operations/help-docs-app.md)
- [Contributing](../CONTRIBUTING.md)
- [Security policy](../SECURITY.md)
- [Release notes](../release-notes/)

## Documentation organization

Keep platform user guides under docs/guides. As the documentation grows, add separate pages under docs/integrations, docs/operations, and docs/troubleshooting instead of expanding the root README.

Lab-specific exercise content belongs under build_files/instructions because Agoge delivers that content inside particular labs. Store future screenshots under docs/assets in a folder named for the guide that uses them.
