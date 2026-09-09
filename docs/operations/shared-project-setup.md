# Shared project setup and API secrets

Run `python setup.py`, select the tenant project, and open **Environment & Quotas → Synchronize Environment Variables**. Choose **All** for a new installation or **Specific** to change one setting.

## Shared hosting settings

The normal setup flow asks for `parent_project`, `parent_dnszone`, `parent_dns_suffix`, and `project_path`. It no longer asks for `dns_suffix`, `dnszone` (sometimes called `dns_zone`), `app_sub_domain`, `main_app_url`, or `firebase_auth_domain`. The old `firebase_auth_subdomain` name is not used by the application.

For example, these settings describe a tenant served at `https://app.example.edu/class-a`:

```json
{
  "project": "tenant-project",
  "parent_project": "parent-project",
  "parent_dnszone": "shared-zone",
  "parent_dns_suffix": ".example.edu",
  "project_path": "class-a"
}
```

This example shows the hosting fields; setup still collects region, zone, admin email, and the other operational settings. The shared load balancer must already exist. Setup adds the tenant's app and API routes after the applications are deployed and ready, as described below.

| Runtime value | Default when the legacy override is absent |
| --- | --- |
| App URL | `https://app.<parent_dns_suffix>/<project_path>` |
| Frontend API origin | `https://api.<parent_dns_suffix>/` |
| Legacy DNS suffix/zone attributes | Parent DNS suffix/zone |
| Firebase auth domain | `<tenant-project>.firebaseapp.com` |

Leading/trailing dots in DNS suffixes and slashes in `project_path` are normalized. Firebase's API key and project ID remain tenant-specific. Authorize the shared app hostname in the tenant's Firebase Authentication settings. Projects with existing custom Firebase hosting retain their explicit `firebase_auth_domain`; the default does not provision a custom authentication domain. See [Firebase's authentication domain guidance](https://firebase.google.com/docs/auth/web/redirect-best-practices) for applications using redirect sign-in.

Existing legacy overrides are preserved and remain editable through **Specific**. Remove an obsolete override from the tenant's `admin-info` environment document when you want the derived default to take effect. Do this after deploying the updated API and cloud functions, because older code requires those fields. Routine upgrades do not delete settings or change secret sources.

## Configure shared load-balancer routing

Full installation and application/function updates configure shared routing after successful deployment. Updating just the main application or cloud function also checks routing once that deployment succeeds. Setup verifies that both Cloud Run services have their latest revisions ready and receiving 100% of traffic, and that the Pub/Sub Cloud Function is active, before publishing a tenant route. The function handles Pub/Sub events and is a readiness prerequisite; it does not receive a public load-balancer route.

For applications deployed manually, or to resume a deferred routing step, run `python setup.py`, select the tenant project, and choose **Application Installation and Updates → Configure Shared Load Balancer Routing**. This operation does not rebuild the applications. The default resource names are `agoge-react`, `agoge-api`, and `agoge` for the Gen 2 Pub/Sub function. If a required deployment is missing or not ready, setup prints commands to inspect the selected tenant and region. Choose **R** to retry after deploying it, **N** to enter different resource names, or **Enter** to defer. Enter service/function names, not URLs. The function must consume the tenant's `agoge` Pub/Sub topic. An incomplete deployment or routing step stops the full install/update before a successful update record is written.

The Cloud Run readiness check accepts observed traffic assigned to `LATEST` or to the latest ready revision by name. It checks the observed `trafficStatuses`, not just the desired `traffic` configuration, and still waits for successful reconciliation. If routing is deferred, the output identifies the failing readiness condition, generation, revision, or traffic allocation. The printed `gcloud run services describe` commands show deployment status without dumping container environment variables. See [Cloud Run's traffic allocation types and reconciliation behavior](https://cloud.google.com/run/docs/reference/rest/v2/projects.locations.services#TrafficTargetAllocationType).

Setup finds the existing global URL map in `parent_project` from the exact host rules for `app.<parent_dns_suffix>` and `api.<parent_dns_suffix>`. It selects a map automatically only when one map has both exact hosts. Otherwise, it prompts for the map name; entering a name confirms that both hosts use that map, and missing exact host rules will be added. This workflow supports one shared URL map for both hosts; configure routing manually if the app and API use separate maps. The URL map's resource name is distinct from a path matcher name such as `app-matcher`; setup reads and updates the complete map instead of importing a path-matcher fragment as a replacement. After successful routing, setup remembers `url_map`, `react_service`, `api_service`, and `function` in the `shared_load_balancer` object of the tenant's Firestore `admin-info/project` document. Update that saved configuration if you later rename resources or change the shared load-balancer topology.

For each Cloud Run service, setup creates or reuses a regional serverless network endpoint group (NEG) and a global `EXTERNAL_MANAGED` backend service in the tenant project. The NEG and Cloud Run service share a region. The parent URL map references these tenant backend services, following [Google Cloud's cross-project backend-service configuration](https://docs.cloud.google.com/load-balancing/docs/https/setup-cross-project-backend-service-backend-bucket) and [serverless load-balancer setup](https://docs.cloud.google.com/load-balancing/docs/https/setup-global-ext-https-serverless).

For `project_path: test-dev`, the routes are:

| Shared host | Paths | Tenant destination | Rewrite |
| --- | --- | --- | --- |
| `app.agoge-labs.com` | `/test-dev`, `/test-dev/*` | React Cloud Run backend | Strip the tenant prefix to `/` |
| `api.agoge-labs.com` | `/test-dev`, `/test-dev/*` | API Cloud Run backend | Strip the tenant prefix to `/` |

Existing tenants, custom backend names, default services, and other routing settings are preserved. Repeating setup reuses compatible resources and routes. Conflicting path ownership or unsupported routing configurations stop the change for manual review; setup does not silently redirect another tenant's traffic. The shared load balancer, HTTPS certificates, public DNS records, and Firebase authorized domains still need to be configured separately.

Before updating the shared URL map, setup validates the backend selection and rewritten paths for both hosts. Its temporary tests use path-only expected outputs because these rules set `pathPrefixRewrite` without `hostRewrite`. A validation failure leaves the shared map unchanged and retains any tenant backends and NEGs already created. Retry the routing menu after resolving the error. Compatible resources are reused without rebuilding the applications.

The account running setup needs permission to read Cloud Run services and Cloud Functions in the tenant, create/read/use its serverless NEGs and backend services, and list/read/validate/update URL maps in the parent, including reading regional/global operation status. Example roles are `roles/run.viewer` and `roles/cloudfunctions.viewer` for readiness checks, `roles/compute.networkAdmin` for tenant Compute resources, and `roles/compute.loadBalancerAdmin` for parent URL-map management; equivalent narrower permissions or existing grants are sufficient. Cross-project references also require `compute.backendServices.use` on the tenant backends, which can be granted to the setup account with `roles/compute.loadBalancerServiceUser` on each backend. Setup does not grant these routing permissions automatically. See [Google Cloud's cross-project IAM requirements](https://docs.cloud.google.com/load-balancing/docs/https/setup-cross-project-backend-service-backend-bucket).

## Choose how each API key is stored

Choose **Specific**, enter `shared_api_secrets`, and select a source for each of `sendgrid_api_key`, `openai_api_key`, and `shodan_api_key`. You can also enter one of those secret names to configure only that key. The same choices appear during **All** setup.

| Choice | Behavior |
| --- | --- |
| Enter — Keep | Leave the current source and value unchanged; the default for existing projects is local. |
| P — Parent reference | Read the same-named secret's `latest` version in `parent_project` at runtime. An old local copy is ignored. |
| C — Copy parent | Read the parent's `latest` version once, add a version to the tenant's same-named secret, and select local storage. Future parent rotations are not copied. |
| L — Local | Enter a tenant key without displaying it, or decline replacement to select an existing enabled local key. Empty input cancels the change. |

Only the three API credentials above can be shared or copied through this flow. Firebase's `api_key`, JWT keys, Guacamole passwords, and the DNS service-account credential remain local. Setting an OpenAI key leaves `rubric_support` unchanged.

Parent reference selection stores only secret names in the tenant environment document:

```json
{
  "shared_api_secrets": [
    "sendgrid_api_key",
    "openai_api_key",
    "shodan_api_key"
  ]
}
```

An absent or empty list means all secrets use local storage. Each selected secret must exist in the parent project with an enabled `latest` version. Missing, disabled, or inaccessible shared secrets fail explicitly; they never fall back to stale local credentials. Running processes may cache a key until their `CloudEnv` instance is recreated, so allow for that when rotating keys. Sharing or copying the same provider key also shares that provider account's usage and quota.

## Permissions and deployment

The account running setup needs metadata access (`secretmanager.versions.get`) on the selected parent secrets. **Copy** additionally requires `secretmanager.versions.access` in the parent and permission to create secrets/add versions in the tenant. **Parent reference** setup checks metadata without reading secret values.

Before API or cloud-function deployment, the build operation checks the selected parent secrets and grants `roles/secretmanager.secretAccessor` on each one to:

```text
agoge-service@<tenant-project>.iam.gserviceaccount.com
```

The deployment account needs `secretmanager.secrets.getIamPolicy` and `secretmanager.secrets.setIamPolicy` on those secrets when a grant is required, plus metadata access for the version check. A secret-level `roles/secretmanager.admin` grant includes these permissions; a custom deployment role can be narrower. The runtime receives only secret-level read access. Existing IAM conditions, other bindings, and policy etags are preserved. See [Google Cloud's secret access guidance](https://cloud.google.com/secret-manager/docs/manage-access-to-secrets) and [Secret Manager roles](https://cloud.google.com/secret-manager/docs/access-control).

These checks run for full installs, updates, API-only deployments, and cloud-function-only deployments. Permission or version failures stop that deployment before the build starts. Frontend-only deployments and projects using only local keys do not require parent-secret IAM access. API provider keys are never written to frontend build files.

Deploy both the API and cloud functions when adopting this change. To return a shared key to local storage, choose **L** or **C**. Old local versions are not deleted by selecting **P**, and switching back to local does not automatically revoke previously granted IAM access; a parent-project administrator can revoke the no-longer-needed secret binding after all consumers have moved.
