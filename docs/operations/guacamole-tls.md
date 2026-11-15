# Shared Guacamole certificate renewal

Agoge's standard workout proxies and managed community proxies can use one wildcard certificate per shared DNS suffix. A certificate-only Pub/Sub Cloud Function in the parent project runs Certbot with Cloud DNS. The function uses its own Google Cloud service account and stores its ACME lineage in a private Cloud Storage bucket. The certificate chain and key are published together to a Secret Manager version. Proxy VMs read the `active` version at boot and refresh it periodically.

## Deploy in the shared project

Run the commands from the Agoge checkout using the setup Python environment. Both the active `gcloud` account and Application Default Credentials need access. Deployment creates the issuer and trigger identities, private state bucket, certificate secret, and function. DNS permissions are granted separately in the project that owns the public managed zone.

Find the public Cloud DNS zone for the suffix first. The DNS project can differ from the project that stores the certificate or Guacamole images.

```sh
gcloud dns managed-zones list --project=DNS_PROJECT
```

Deploy the issuer, substituting the DNS project, zone name, and ACME contact.

```sh
python setup.py guacamole-tls deploy \
  --project agoge-shared-resources \
  --domain agoge-labs.com \
  --dns-project DNS_PROJECT \
  --dns-zone DNS_ZONE \
  --email ACME_CONTACT
```

For an ACME test, run the same command with `--staging` first. Staging has a separate function, schedule, bucket, and secret. Use a distinct bucket if supplying a custom bucket name. Tenant enrollment uses the production secret.

The production deploy reuses the parent's enabled `agoge-hourly-maintenance` scheduler when it publishes Agoge maintenance events. Set `--scheduler-region` if that job lives outside the function region. If the shared job is absent, setup provisions a certificate-only Pub/Sub schedule at midnight in the configured timezone. The function filters for maintenance events, and a Cloud Storage lease guards overlapping deliveries. Certificate renewal stays independent of the tenant maintenance routines that stop lab servers or take snapshots.

For the dedicated trigger, setup prints a Pub/Sub command to run the first check immediately. When reusing the parent's maintenance schedule, the function checks on the next daily tick. Confirm the function logged a successful publication and verify the enabled version metadata before enrolling tenants.

```sh
gcloud secrets versions describe active \
  --secret=guacamole-tls-agoge-labs-com --project=agoge-shared-resources
```

Add `--notification-channel projects/PROJECT/notificationChannels/CHANNEL_ID` to the deploy command to configure a Cloud Monitoring log alert. Issuer logs contain the expiration date, version number, and sanitized operational errors. Issuance failures and certificates approaching expiry are reported as errors.

## Enroll child projects

Deploy the updated Agoge API and Cloud Function to the pilot tenant. Deploy the updated frontend there to activate CORE branding.

The enrollment command validates the tenant's DNS suffix and configured parent against the shared certificate and the DNS project recorded at issuer deployment. It creates a dedicated `agoge-guac-tls` reader in the tenant, grants it access on the shared certificate secret, and writes the reference to the tenant's `admin-info/project` document. Standard workout proxies use that reader. Managed community proxies retain their Unit identity and can impersonate the reader for the certificate only. The Unit signing secret continues to use its own permission.

```sh
python setup.py guacamole-tls reconcile \
  --project agoge-shared-resources --domain agoge-labs.com \
  --allow TENANT_PROJECT
```

Use additional `--allow` flags to enroll other child projects using the same parent and suffix. The command can be rerun to reconcile permissions. Use `--remove TENANT_PROJECT` when a child project is retired to remove the shared certificate grant and tenant opt-in. Rotate the wildcard key if it has been exposed.

## Update existing proxies

Run the inventory first. Use `--instance` with a full VM name to pilot on one standard proxy and one managed community proxy before applying it project-wide.

```sh
python setup.py guacamole-tls migrate --project TENANT_PROJECT
python setup.py guacamole-tls migrate --project TENANT_PROJECT --apply
```

Stopped VMs receive the startup settings and remain stopped until their normal start. For running proxies with the required identity, setup attempts a live install using existing trusted SSH access. When that access is unavailable, setup reports that the installer is staged for the next boot. If a running proxy needs a service account change, re-run with `--apply --restart-running` in a maintenance window. A stop/start can briefly interrupt sessions or change its public IP. The migration refreshes the DNS record if the address changes.

The guest verifies the certificate and key before switching them together, then checks the certificate served by Nginx after a graceful reload. If a refresh fails, the guest keeps the previous local certificate. Verify the certificate on a new HTTPS connection and check that an already-open desktop survives a rotation in the pilot.

## Use a Guacamole image without a bundled wildcard key

Build a clean Guacamole source image once in a project with access to `image-guac-base`. The image builder uses that project's default VPC and a temporary VM. The output has a separate name, such as `image-guac-tls-agoge-shared-resources`. Use a new versioned `--image-name` when updating the image. Grant the tenant's `agoge-service` identity the Compute Image User role on the image if it lives in another project.

```sh
python setup.py guacamole-tls build-image --project agoge-shared-resources
python setup.py guacamole-tls reconcile \
  --project agoge-shared-resources --domain agoge-labs.com \
  --allow TENANT_PROJECT \
  --image projects/agoge-shared-resources/global/images/image-guac-tls-agoge-shared-resources
```

Boot and verify a new standard proxy and a new managed community proxy before applying the image to additional tenants. The image setting applies to later boots from newly created disks. The migration command updates existing disks in place.

## Recover from a failed rotation

Inspect the function logs and the guest's `agoge-guacamole-tls.service` journal. If the active version is unusable and a valid `previous` version remains, pause the certificate issuer before reverting the `active` alias. For an issuer using the shared maintenance schedule, disable the separate issuer identity during recovery so normal Agoge maintenance can continue. Update the aliases using the version numbers from Secret Manager. Confirm the guest refresh and then resume issuance.
