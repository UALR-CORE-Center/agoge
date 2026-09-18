# Deploying shared image editing

Shared image checkout creates an editing VM and snapshots in the current site's project. An administrator's **Save shared image** action replaces the production image at its original project and image name. Other sites continue using that image reference for future builds; existing lab VMs are not rebuilt. Template settings such as machine type, description, and connection settings remain in the current site's catalog.

## Rollout

Deploy the cloud function, API, and frontend from the same revision. Pause template editing during rollout, deploy the cloud function first, then the API, then the frontend. The updated function rejects shared mutation messages without API authorization; an old API cannot supply that authorization. Do not enable shared editing against an older function, which could save the image into the site's project.

The updated API derives `is_shared`, `source_project`, and `can_edit_shared` from stored image references and the authenticated user's role. No catalog migration is required. Shared checkout, check-in, and settings changes require explicit warning acknowledgment. Non-administrators can copy the saved image to a distinct local name. Shared deletion and user-initiated snapshot changes are unavailable; check-in creates its internal snapshot automatically.

## Runtime permissions

The setup code configures `agoge-service@<site-project>.iam.gserviceaccount.com` for API and function execution. Verify the deployed identities, particularly for installations with customized deployment settings:

```shell
gcloud run services describe agoge-api --project=SITE_PROJECT --region=REGION --format="value(spec.template.spec.serviceAccountName)"
gcloud functions describe agoge --gen2 --project=SITE_PROJECT --region=REGION --format="value(serviceConfig.serviceAccountEmail)"
```

Existing bootstrap code grants `roles/compute.imageUser` in `BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT` through `ShellCommands.SharedResourcePermissions`. It does **not** grant shared image creation or deletion. Local project ownership does not supply access in the shared image's project. A shared-project administrator must arrange the additional runtime permissions before direct editing is used; this feature does not expand IAM grants automatically.

| Operation | Shared image project | Current site project |
| --- | --- | --- |
| Copy to local image, performed by the API | Read and use the source image (`compute.images.get`, `compute.images.useReadOnly`) | Create/read the new image, read operation status, inspect existing VM/disk names, and create the catalog record |
| Edit and publish shared image, performed by the function | Read/use/create/delete the original image and read its global operation status (`compute.images.get`, `compute.images.useReadOnly`, `compute.images.create`, `compute.images.delete`, `compute.globalOperations.get`) | Existing template VM, disk, DNS, and snapshot permissions, including using the snapshot as an image source (`compute.snapshots.useReadOnly`) |

Apply these permissions to the actual source project recorded in the image URL; imported images can use a different project from the setup default. Existing equivalent grants suffice. Prefer a narrowly scoped role for shared publishing over project ownership. These permissions cover the added image operations; existing runtime permissions for Firestore, Pub/Sub, and local server management are still required. No shared-project Firestore write access is introduced.

Google documents source-image/source-snapshot authorization in [images.insert](https://docs.cloud.google.com/compute/docs/reference/rest/v1/images/insert), replacement deletion in [images.delete](https://docs.cloud.google.com/compute/docs/reference/rest/v1/images/delete), and operation visibility in [globalOperations.get](https://docs.cloud.google.com/compute/docs/reference/rest/v1/globalOperations/get).

## Interrupted copy recovery

The API waits for the new local image to be ready before creating its editable catalog record. It never overwrites an existing image, VM, disk, or template with the requested name.

A timeout or connection loss can occur after Compute accepted the image copy. A concurrent catalog creation can also prevent the final record write. In either case, a local image may remain without a new template record. Repeating the same name then returns a conflict rather than replacing the resource.

1. Refresh the image list first; the original request may have completed successfully. If the named local template exists, use it.
2. If it does not, inspect the local `image-<requested-name>` image, its creation operation, and the site's catalog. Wait for an in-progress operation to settle.
3. Use a different new name to retry without touching existing resources. An administrator can separately clean up a confirmed unused copy after verifying that no template or lab references it. Do not delete the original shared image or an existing VM/disk to force the name to work.

If shared check-in fails, the edit reservation and working resources are retained. Inspect the function's error and image operation in the source project, correct the cause, and retry saving. Replacement uses a delete/create operation, so a failure between those steps can temporarily leave the shared image unavailable for new builds. Coordinate recovery before other sites launch new labs from that image.

## Validation

Automated tests cover authorization, acknowledgment, source-project preservation, local copying, conflicts, cancellation, and snapshot bypasses using mocked cloud clients. They do not verify live IAM, cross-project image publishing, or deployed GCP resources. Exercise a disposable shared image with an instructor and an administrator after deployment before changing a production image.
