# Help documentation web app

The application's **Help & Documentation** button opens `/help` within the
current site, such as `/test-dev/help`. The help pages are public and use the
Markdown files in this repository's `docs/` directory. They do not require an
Agoge API request or instructor sign-in.

## Edit and preview

Edit the original Markdown under `docs/`. Headings become linkable anchors;
relative Markdown links stay inside the help app, and relative images and
example downloads are included in the build. Links outside `docs/` open the
corresponding source in GitHub. Raw HTML is not executed.

From `frontend/`, run:

```bash
npm start
```

Open `http://localhost:3000/help`. Restart the frontend dev command after editing
Markdown to regenerate the help content. Search matches article titles and full
Markdown text. JSON examples remain downloadable files rather than appearing as
articles in navigation.

## Build and deploy

`npm run build` first runs `scripts/build-help.mjs`, which creates a searchable
manifest and copies documentation assets into the generated
`frontend/public/help-content/` directory. The source remains `docs/`; do not edit
the generated files.

Use setup's normal **Update Main Application → React** deployment. Setup stages
the current `docs/` tree as `frontend/.help-docs` before submitting the frontend
Docker context, then restores/removes that temporary copy when the build ends.
The Docker build generates the same help content from this staged source. A
missing Markdown source stops the build with an explanation instead of shipping
an empty help site.

For a manual frontend-only Docker or Cloud Build submission, copy `docs/` to
`frontend/.help-docs/` before creating the build context. The staged source must
include `README.md`; the build does not download documentation from another
server. Remove the staging directory afterward.

Deploy the frontend again after editing Markdown to publish the changed help
pages. No separate host, DNS record, or documentation service is needed.

## Verify

```bash
cd frontend
npm run test:help-build
npm test -- src/components/Help/HelpApp.test.tsx
npm run build
```

Open the deployed site's Help button, search for an article, follow a relative
guide link, and reload a deep URL such as
`/test-dev/help/operations/wireguard-provisioning`.
