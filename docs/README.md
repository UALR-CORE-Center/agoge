# Agoge Documentation

Agoge documentation is organized by audience. These pages describe the current interface and workflows on the main branch.

## User guides

| Audience | Guide | Covers |
| --- | --- | --- |
| Instructors | [Instructor Guide](guides/instructor-guide.md) | Building and distributing labs, creating templates, managing learner workouts, reusable server images, and snapshots |
| Learners | [Learner Guide](guides/learner-guide.md) | Claiming a lab, starting servers, connecting with RDP, SSH, or Guacamole, managing session time, and completing assessments |

## Project documentation

- [Project overview and deployment](../README.md)
- [Shared project setup and API secrets](operations/shared-project-setup.md)
- [Community WireGuard example](examples/community-wireguard.md)
- [Contributing](../CONTRIBUTING.md)
- [Security policy](../SECURITY.md)
- [Release notes](../release-notes/)

## Documentation organization

Keep platform user guides under docs/guides. As the documentation grows, add separate pages under docs/integrations, docs/operations, and docs/troubleshooting instead of expanding the root README.

Lab-specific exercise content belongs under build_files/instructions because Agoge delivers that content inside particular labs. Store future screenshots under docs/assets in a folder named for the guide that uses them.
