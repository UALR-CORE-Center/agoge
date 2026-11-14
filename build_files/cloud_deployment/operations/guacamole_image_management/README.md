# Guacamole project image setup

Use **Server Images & Build Specs → Refresh/Create guacamole image and certificate.** in `python setup.py` to retry this step independently of the application deployments.

When the selected project already has `image-guac-<project-id>`, setup boots the temporary VM from that image. Certbot renews the wildcard certificate when it is due. Setup reads the certificate fingerprint from the builder's serial output, checks that the VM serves that certificate, and saves the replacement under the same image name. The account running setup needs `compute.instances.getSerialPortOutput` on the builder VM.

When the project image is absent, setup uses `image-guac-base` from `default_server_image_project`, `parent_project`, or the tenant project in that order. The account running setup needs read and use access to the source image. Setup validates the source before reading startup secrets, replacing the Firestore image record, or creating the VM.

To inspect an existing project image or the configured shared base, use:

```shell
gcloud compute images describe image-guac-PROJECT_ID --project=PROJECT_ID
gcloud compute images describe image-guac-base --project=BASE_IMAGE_PROJECT_ID
```

Creating a Firestore `image` document only registers the template; it does not create the underlying Compute Engine image. The temporary VM and the resulting customized image still belong to the tenant project. A missing or inaccessible base image stops setup with the source project's name in the error.

Older setup logs included full Firestore document contents, including the Guacamole startup script's credentials. If a log contains a private key or passwords, replace/revoke the exposed DNS service-account key and update `google_dns_service_key` in the tenant's Secret Manager. Rotate the exposed Guacamole/MySQL credentials there as well, coordinate changes with any existing servers, and rerun this step to regenerate the startup script and project image. Updated Firestore reads log document IDs only; the temporary DNS credential file is created with mode `0600`.

For details about the server configuration, see the deployment [README](/build_files/server_config/guacamole/README.md).
