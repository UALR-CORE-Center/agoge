# Agoge

Agoge is a hands-on cybersecurity lab environment fully built and managed in Google Cloud.

## Introduction
Agoge is a cloud-native cybersecurity training environment built on Google Cloud Platform (GCP).  
It allows instructors to deploy hands-on attack and defense labs for large groups of learners with minimal infrastructure management.

Instructors can select pre-built labs from the Agoge library or create their own. When a training environment is launched, Agoge automatically provisions the required infrastructure for each student. Builds typically complete in 5–10 minutes, after which learners can access their labs via browser-based connections.

Students can independently start and stop their lab environments, allowing cloud resources to be used only when needed.

Agoge is designed for environments that require scalable
cybersecurity training infrastructure, including:

- University cybersecurity programs
- Cybersecurity clinics
- Cyber defense competitions
- Workforce development training
- Government and military cyber exercises

## Quick Start

1. Install the Google Cloud SDK
2. Clone the repository

```bash
git clone https://github.com/UALR-CORE-Center/agoge.git
cd agoge
python setup.py
```

## Key Features
- Cloud-native cybersecurity training environments
- Automated lab provisioning for large classes
- Cost-efficient resource usage through on-demand infrastructure
- Browser-based student access (no local installation required)
- Works within restricted institutional networks
- Multi-tenant architecture for shared lab infrastructure

## Documentation

- [Instructor Guide](docs/guides/instructor-guide.md)
- [Learner Guide](docs/guides/learner-guide.md)
- [Documentation Index](docs/README.md)

## Architecture Overview
Agoge runs entirely in Google Cloud and uses several managed services:
- **Cloud Run** – hosts the Agoge API and web application
- **Cloud Functions** – orchestrates infrastructure provisioning
- **Firestore** – stores configuration and lab state
- **Compute Engine** – runs student lab environments
- **Cloud DNS** – dynamically generates lab DNS records
- **Cloud Load Balancing** – routes traffic to multiple training environments

The platform supports multi-tenant deployments where multiple training environments share a central resource project.

## Project Status
Agoge is actively developed and maintained by the UALR CORE Center.

The platform is currently used for cybersecurity education and research environments. Contributions and feedback from 
the academic and security communities are welcome.

## Deploying **Agoge**
Agoge’s **`setup.py`** script turns a bare GCP project into a fully-provisioned Agoge environment.
Most deployments use the script to 1) create a fresh customer-specific project, and 2) connect it to the shared-resource project that holds common images, Firestore data, and configuration. (You *can* run the stack in a one-off project, but you’ll lose the benefits of centralised assets and cross-project sync.)

---

### 1  Prerequisites

| Tool / File                              | Why you need it                                                                      | Quick install / notes                                                                                               |
| ---------------------------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| **Google Cloud SDK**                     | CLI used by the setup script                                                         | `https://cloud.google.com/sdk/install`                                                                              |
| **PyCharm** (or another IDE)             | Easiest way to run and debug `setup.py`                                              | `https://www.jetbrains.com/pycharm/`<br>Mark `build_files/`, `cloud_functions/`, and `main_app/` as *Sources Root*. |
| **`environments.json`** <br>*(optional)* | Lets you deploy **into an existing project** instead of having the script create one | Copy `build_files/install_update/environments.sample.json` → `environments.json`, then add an entry:  \`\`\`json    |
| {                                        |                                                                                      |                                                                                                                     |
| "my-agoge-test": {                       |                                                                                      |                                                                                                                     |

```
"impersonation_account": "sa-deploy@my-agoge-test.iam.gserviceaccount.com",
"project_id": "my-agoge-test"
```

}
}

````Leave this file out entirely when doing the normal *central deployment* flow. |

> **Permissions check**The service account listed above must have `roles/editor` (minimum) on the target project **and** access to the shared-resource project.

---

### 2  Run the setup script

```bash
python setup.py
````

If setup reports missing/expired credentials, appears to wait for an invisible
authentication prompt, or you changed Google accounts, run a complete local
credential refresh first:

```bash
python setup.py --reauthenticate
```

This opens the normal browser sign-in and synchronizes both credential stores
used by setup: the active `gcloud` login and Application Default Credentials
(ADC) used by the Python Google Cloud clients. The same action is available
under **Environment & Quotas → Refresh gcloud and Python GCP Credentials**.

Project creation also requires `roles/resourcemanager.projectCreator` on the
configured production or development folder. The defaults can be overridden
without editing source code by setting `AGOGE_PRODUCTION_FOLDER_ID`,
`AGOGE_DEVELOPMENT_FOLDER_ID`, and `AGOGE_BILLING_ACCOUNT_ID`.

The wizard will:

1. Create / select the customer project.
2. Enable required APIs.
3. Copy base server images from the shared-resource project.
4. Deploy Cloud Run services and Cloud Functions.
5. Prompt you for an admin email used for Firebase / IAM bootstrap.

### 3  Post-deployment tasks

| Task                | Where to do it         | Details                                                                                                                                                                                                                                                                                 |
| ------------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Domain mappings** | Cloud Run → *Domains*  | Map `api.<your-domain>` → API service, `app.<your-domain>` → React front-end.                                                                                                                                                                                                           |
| **Quota boosts**    | IAM & Admin → *Quotas* | Set limits using the table below (MCB = Max Concurrent Builds).<br><br> <ul><li>Subnetworks = MCB × 2</li><li>Networks = MCB × 1</li><li>Firewall Rules = MCB × 3</li><li>Routes = MCB × 2</li><li>In-Use IPs = MCB × 1</li><li>CPUs = MCB × 3</li><li>Concurrent Builds = 50</li></ul> |

---

### 4  Firebase & SSO (Configuration steps directed during the setup script)

1. **DNS records**
   * `api.<your-domain>` → Cloud Run default CNAME-record.
   * `app.<your-domain>` → Cloud Run default CNAME-record.
   * `auth.<your-domain>` → CNAME to `<project>.web.app.`

2. **Firebase console → Build ▸ Authentication**

   * *Settings* → **Authorized domains** → add `app.<your-domain>`, `auth.<your-domain>`, `127.0.0.1`.
   * *Hosting* → “Add custom domain” → `auth.<your-domain>` (choose *serve traffic*).

3. **Google Cloud console → APIs & Services ▸ OAuth 2.0**

   * Create / edit a **Web application** client.
   * **Authorized JavaScript origins** → same list as Firebase.
   * **Authorized redirect URIs** →

     * `https://<project>.firebaseapp.com/__/auth/handler`
     * `https://auth.<your-domain>/__/auth/handler`

### 5  Automating quota changes (optional)

Agoge supports the **Cloud Quotas API**. See `build_files/quota_manager.py` for an example that:

* Lists adjustable quotas (`quota_infos`).
* Creates / updates `QuotaPreference` objects for CPUS, NETWORKS, etc.
* Falls back to a Support case when a quota needs manual approval.

## Running Deployment, Updates, and Administration Scripts

All administrative scripts for deploying, updating, and maintaining the Agoge application and cloud environment reside 
in `build_files/cloud_deployment`. They’re organized into categories defined in 
`cloud_deployment/utilities/menu_options.py`.

### Adding a New Script

1. **Choose a Category**  
   In `SetupCategories`, place your script under the correct top-level category. If you add a new category, also add 
its label to the `category_menu` dictionary.
   ```python
   class SetupCategories(Enum):
       APP_INSTALL_UPDATES = 1
       IMAGES_AND_SPECS = 2
       ENV_AND_QUOTAS = 3
       PROJECTS = 4
       EXIT = 5
   ```

2. **Create a Menu Item**  
   In `SetupOptions`, add a new enumeration representing your script. Then, add it to `category_menu`:
   ```python
   class SetupOptions(bytes, Enum):
       FULL = (0, "Full Agoge Installation")
       ...
       NEW_COMMAND = (99, "New command description")
       ...
   ```

3. **Implement the Script**  
   Place your script as a class in the appropriate folder under `build_files/cloud_deployment/operations`.

4. **Link to the Menu**  
   In `build_files/cloud_deployment/setup_manager.py`, tie it into the `operation_map` to run your new script:
   ```python
   operation_map = {
       SetupOptions.FULL: self._run_full_install,
       ...
       SetupOptions.NEW_COMMAND: lambda: NewFunctionManager().run(),
       ...
   }
   ```
   
## Load Balancing Setup (Parent Project and Child Projects)

Agoge routes multiple child projects through one public entrypoint in the parent project. It uses path based routing
so each child project is reached through a URL prefix like `/school-one/` or `/project-two/`.

If someone visits `app.<PARENT_DOMAIN>` or `api.<PARENT_DOMAIN>` without a valid child prefix, the request falls back
to the parent project's default backend bucket (`default-404-backend`).

> Placeholders used below:
> - `<PARENT_DOMAIN>`: parent domain (example: `example.com`)
> - `<PARENT_PROJECT_ID>`: parent GCP project id that hosts the load balancer (example: `parent-shared-123456`)
> - `<CHILD_PROJECT_ID>`: child GCP project id (example: `child-project-123456`)
> - `<CHILD_PROJECT>`: child backend name prefix (example: `child-project`)
> - `<CHILD_PROJECT_PATH>`: path prefix used for routing (example: `school-one`)

---
### 1. Child project backend services (per child project)

In the child GCP project, create two global backend services pointing to Cloud Run using serverless NEGs.

#### 1.1 React backend service

1. Go to **Network services** → **Backends**
2. Click **Create backend service**
3. Set:
   - **Backend service type:** Global backend service
   - **Name:** `<CHILD_PROJECT>-react`
   - **Load balancer type:** Global external application load balancer
   - **Backend type:** Serverless network endpoint group
4. Under **Backends**, add a backend:
   - Select `<CHILD_PROJECT>-react`
   - If it is not listed, create a serverless NEG:
     - **Name:** `<CHILD_PROJECT>-react`
     - **Region:** `us-central1`
     - **Type:** Cloud Run
     - **Service:** `agoge-react`
5. Disable **Cloud CDN**
6. Click **Create**

#### 1.2 API backend service

1. Go to **Network services** → **Backends**
2. Click **Create backend service**
3. Set:
   - **Backend service type:** Global backend service
   - **Name:** `<CHILD_PROJECT>-api`
   - **Load balancer type:** Global external application load balancer
   - **Backend type:** Serverless network endpoint group
4. Under **Backends**, add a backend:
   - Select `<CHILD_PROJECT>-api`
   - If it is not listed, create a serverless NEG:
     - **Name:** `<CHILD_PROJECT>-api`
     - **Region:** `us-central1`
     - **Type:** Cloud Run
     - **Service:** `agoge-api`
5. Disable **Cloud CDN**
6. Click **Create**

---

### 2. Parent project load balancer (create once)

In the parent GCP project, create the load balancer and then add child projects as cross project backend services.

#### 2.1 Create the load balancer

1. In the parent GCP project, go to **Network services** → **Load balancing**
2. Click **Create load balancer**
3. Set:
   - **Type:** Application Load Balancer (HTTP/HTTPS)
   - **Facing:** Public facing (external)
   - **Deployment:** Best for global workloads
   - **Generation:** Global external application load balancer
4. Click **Create**

#### 2.2 Frontend configuration

Add two frontends.

HTTP frontend:
- **Name:** `http-frontend`
- **Protocol:** HTTP
- **IP version:** IPv4
- **IP address:** Ephemeral
- **Port:** 80

HTTPS frontend:
- **Name:** `agoge-shared-labs-frontend`
- **Protocol:** HTTPS
- **IP version:** IPv4
- **IP address:** Ephemeral
- **Port:** 443
- **SSL policy:** GCP default
- **HTTP/3 (QUIC):** Automatic (default)
- **Early data (0-RTT):** Disabled

Certificate:
- Select an existing certificate, or create a Google managed certificate:
  - **Name:** `agoge-labs-cert`
  - **Create mode:** Create Google managed certificate
  - **Domains:**
    - `api.<PARENT_DOMAIN>`
    - `app.<PARENT_DOMAIN>`

#### 2.3 Backend configuration

1. In **Backend services & backend buckets**, set the default backend to:
   - `default-404-backend`
2. If `default-404-backend` does not exist yet, create it as a backend bucket in the parent project:
   - **Name:** `default-404-backend`
   - **Cloud CDN:** Disabled
3. In **Cross project backend services & backend buckets**, add the child project backends:
   - **Project id:** `<CHILD_PROJECT_ID>`
   - Select:
     - `<CHILD_PROJECT>-react`
     - `<CHILD_PROJECT>-api`

Repeat the cross project backend step for each child project you want to route.

#### 2.4 Routing rules

Set **Routing rules** mode to **Advanced host and path rule**.

1. Default host and path rules:
   - **Action:** Route traffic to a single backend
   - **Backend:** `default-404-backend`

2. Add a host rule for the React app:
   - **Hosts:** `app.<PARENT_DOMAIN>`
   - **Path matcher:** `app-matcher`

3. In the **Path matcher** editor, paste and maintain rules in this format:

```yaml
defaultService: projects/<PARENT_PROJECT_ID>/global/backendBuckets/default-404-backend
name: app-matcher
pathRules:
  - paths:
      - /<CHILD_PROJECT_PATH>/*
    service: projects/<CHILD_PROJECT_ID>/global/backendServices/<CHILD_PROJECT>-react
    routeAction:
      urlRewrite:
        pathPrefixRewrite: /
```

4. Add another host and path rule for the API:
   - **Hosts:** `api.<PARENT_DOMAIN>`
5. In the **Path matcher** editor, paste and maintain rules in this format:

```yaml
defaultService: projects/<PARENT_PROJECT_ID>/global/backendBuckets/default-404-backend
name: api-matcher
pathRules:
  - paths:
      - /<CHILD_PROJECT_PATH>/*
    service: projects/<CHILD_PROJECT_ID>/global/backendServices/<CHILD_PROJECT>-api
    routeAction:
      urlRewrite:
        pathPrefixRewrite: /
```

6. Click **Create**
---

### 3. setup.py configuration required

In `setup.py`, you need to add new environment variables to each child project so it can route through the parent load balancer.

#### 3.1 Add variables using setup.py

In the menu select:  
`3. Environment & quotas` then `1. Synchronize Environment Variables`

When prompted:  
`Do you want to update a specific environment variable or ALL environment variables for <CHILD_PROJECT_ID>? [s]pecific/[A]ll`  
Choose: `s`

When prompted:  
`Which variable do you want to update?`  
Enter the variable name (example: `parent_dns_suffix`) and set it to the desired value.

Repeat this for each required variable below.

#### 3.2 Required environment variables

| Variable          | Example value        | Notes                                                                            |
|-------------------|----------------------|----------------------------------------------------------------------------------|
| parent_dns_suffix | .example.com         | Parent DNS suffix used for shared routing                                        |
| parent_dnszone    | example-com          | Cloud DNS zone name, not the domain                                              |
| parent_project    | parent-shared-123456 | Parent project id hosting the load balancer and DNS                              |
| project_path      | school-one           | Must match the path used in the parent load balancer matchers: /<project_path>/* |
> Tip: project_path controls the URL prefix for that child project.
> Example: project_path=school-one routes app.<PARENT_DOMAIN>/school-one/ and api.<PARENT_DOMAIN>/school-one/.


## Citation

If you use Agoge in academic research, please cite the following work:

Huff, Philip, Sandra Leiterman, and Jan P. Springer. 
"Cyber arena: an open-source solution for scalable cybersecurity labs in the cloud." 
Proceedings of the 54th ACM Technical Symposium on Computer Science Education V. 1. 2023.

Example BibTeX:
```bibtex
@inproceedings{huff2023cyber,
  title={Cyber arena: an open-source solution for scalable cybersecurity labs in the cloud},
  author={Huff, Philip and Leiterman, Sandra and Springer, Jan P},
  booktitle={Proceedings of the 54th ACM Technical Symposium on Computer Science Education V. 1},
  pages={221--227},
  year={2023}
}
```

## License
See the [License](LICENSE) file.
