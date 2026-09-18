# Register existing GCP server images

An image in Compute Engine must also have an Agoge record before it appears in the app's server image library. Registration stores the image reference and connection settings in Firestore; it does not upload or copy the image's disk contents.

1. Run `python setup.py` and select the project containing the existing Compute Engine images.
2. Open **Server Images & Build Specs → Import Custom Images from GCP into App**.
3. Check the project and database printed by the importer. It uses the selected project's **agoge-v1** Firestore database and **image** collection.
4. Answer **y** for each image you want to register. Press Enter or answer **n** to skip an image.
5. Configure **Human Interaction** if learners need SSH or RDP access, using the credentials already configured on the image.
6. Wait for the **Saved** confirmation. Each accepted image is committed before the next image prompt. Registration does not require a corresponding lab or create a lab specification.
7. Refresh **Teachers → Manage Servers** in the app using that project's image library, then select the registered image when building a template.

The confirmation includes the Firestore document path. For example:

| Compute Engine image | Firestore document in `agoge-v1` |
| --- | --- |
| `image-csec2324-proxychain-host` | `image/csec2324-proxychain-host` |

Agoge removes the `image-` prefix from the document ID but retains the full Compute Engine image name in the record's `image` field. Already registered images are skipped when you rerun the import.

If a save fails, the importer reports the error and does not count that image as imported. Check the final imported, skipped, and failed counts. A failure to read the existing image records stops the import before any writes.

Older versions asked a second question about adding images with corresponding labs. Answering **n** there discarded images already accepted earlier in the session. After updating the setup code, rerun the import and select those images again.
