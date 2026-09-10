# Agoge frontend

React application for the Agoge web UI.

## Firebase configuration

Follow the [Firebase authentication setup guide](../docs/operations/firebase-authentication.md) for console settings, the `test-dev` example, and login troubleshooting. The setup script generates `frontend/.env.production` for the selected child project before Cloud Build:

| Build variable | Source |
| --- | --- |
| `VITE_FIREBASE_KEY` | Child project's `api_key` secret, from its Firebase Web app SDK configuration |
| `VITE_FIREBASE_AUTH_DOMAIN` | Selected `firebase_auth_domain`; defaults to `<child-project>.firebaseapp.com` |
| `VITE_PROJECT_ID` | Child GCP/Firebase project ID |
| `VITE_PROJECT_PATH` | Tenant path, such as `/test-dev/` |
| `VITE_AGOGE_API_URL` | Shared API origin, such as `https://api.agoge-labs.com/` |

Vite embeds these values in JavaScript. Rebuild through **Update Main Application Only → Specific → React** after changing them; Cloud Run runtime environment edits do not update an existing bundle. Setup restores local environment files after the build, so inspect the build output and deployed app when checking the effective configuration.

## MUI X

The frontend uses the MIT-licensed MUI X Community Data Grid and date pickers.
No MUI X commercial license key or `VITE_MUI_LICENSE` setting is required for
local development or production builds.

The shared data grid supports search, single-column filtering and sorting,
checkbox selection, and pagination. Pages are limited to 100 rows, matching the
existing page-size options; datasets can contain more than 100 records. Pro
features such as multi-column sorting/filtering, column pinning, and drag-and-drop
column reordering are not available.
