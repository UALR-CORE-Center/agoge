# Guacamole project image setup

Use **Server Images & Build Specs → Refresh/Create guacamole image and certificate.** in `python setup.py` to retry this step independently of the application deployments.

The Guacamole base image must already exist in Compute Engine as `image-guac-base`. Setup resolves it from `default_server_image_project`, falling back to `parent_project`, then the tenant project when neither setting is present. The account running setup must be able to read and use that image. Setup validates the image before reading startup secrets, replacing the Firestore image record, or creating the VM.

For a shared image project named `agoge-shared-resources`, check the source with:

```shell
gcloud compute images describe image-guac-base --project=agoge-shared-resources
```

Creating a Firestore `image` document only registers the template; it does not create the underlying Compute Engine image. The temporary VM and the resulting customized image still belong to the tenant project. A missing or inaccessible base image stops setup with the source project's name in the error.

Older setup logs included full Firestore document contents, including the Guacamole startup script's credentials. If a log contains a private key or passwords, replace/revoke the exposed DNS service-account key and update `google_dns_service_key` in the tenant's Secret Manager. Rotate the exposed Guacamole/MySQL credentials there as well, coordinate changes with any existing servers, and rerun this step to regenerate the startup script and project image. Updated Firestore reads log document IDs only; the temporary DNS credential file is created with mode `0600`.

For details about the server configuration, see the deployment [README](/build_files/server_config/guacamole/README.md).
