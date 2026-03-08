from enum import Enum
import os

from google.auth import impersonated_credentials, default


class ShellCommands:   
    class EnableAPIs(str, Enum):
        COMPUTE = "gcloud services enable compute.googleapis.com"
        FUNCTIONS = "gcloud services enable cloudfunctions.googleapis.com"
        CLOUD_BUILD = "gcloud services enable cloudbuild.googleapis.com"
        PUB_SUB = "gcloud services enable pubsub.googleapis.com"
        RUNTIME_CONFIG = "gcloud services enable runtimeconfig.googleapis.com"
        CLOUD_RUN = "gcloud services enable run.googleapis.com"
        SCHEDULER = "gcloud services enable cloudscheduler.googleapis.com"
        APP_ENGINE = "gcloud services enable appengine.googleapis.com"
        IAM = "gcloud services enable iam.googleapis.com"
        DNS = "gcloud services enable dns.googleapis.com"
        FIRESTORE = "gcloud services enable firestore.googleapis.com"
        IDENTITY_TOOLKIT = "gcloud services enable identitytoolkit.googleapis.com"
        CLOUD_SUPPORT = "gcloud services enable cloudsupport.googleapis.com"
        SECRET_MANAGER = "gcloud services enable secretmanager.googleapis.com"
        EVENT_ARC = "gcloud services enable eventarc.googleapis.com"
        QUOTAS = "gcloud services enable cloudquotas.googleapis.com"
        CLOUD_DNS = "gcloud services enable dns.googleapis.com"
        CLOUD_DOMAINS = "gcloud services enable domains.googleapis.com"

    class Impersonation(str, Enum):
        CREATE_IDENTITY_POOL = "gcloud iam workload-identity-pools create {project}-labs-pool " \
                               "--location=\"global\" --description=\"Workload Identity Pool for local development\" " \
                               "--display-name=\"LocalDevPool\""
        CREATE_OIDC = "gcloud iam workload-identity-pools providers create-oidc {project}-provider " \
                      "--location=\"global\" --workload-identity-pool={project}-labs-pool " \
                      "--display-name=\"LocalDevProvider\" " \
                      "--attribute-mapping=\"google.subject=assertion.sub,attribute.email=assertion.email\" " \
                      "--issuer-uri=\"https://accounts.google.com\""

    class ServiceAccount(str, Enum):
        CREATE_AGOGE_ACCOUNT = "gcloud iam service-accounts create agoge-service --display-name " \
                               "\"Agoge Service Account\""
        ADD_AGOGE_ROLE_OWNER = "gcloud projects add-iam-policy-binding {project} " \
                               "--member=serviceAccount:agoge-service@{project}.iam.gserviceaccount.com " \
                               "--role=\"roles/owner\" --condition=None"
        ADD_AGOGE_ROLE_PUBSUB = "gcloud projects add-iam-policy-binding {project} " \
                                "--member=serviceAccount:agoge-service@{project}.iam.gserviceaccount.com " \
                                "--role=\"roles/pubsub.admin\" --condition=None"
        ADD_AGOGE_ROLE_STORAGE = "gcloud projects add-iam-policy-binding {project} " \
                                 "--member=serviceAccount:agoge-service@{project}.iam.gserviceaccount.com " \
                                 "--role=\"roles/storage.admin\" --condition=None"
        ADD_AGOGE_ROLE_IMAGE_READER = "gcloud projects add-iam-policy-binding {project} " \
                                      "--member=serviceAccount:agoge-service@{project}.iam.gserviceaccount.com " \
                                      "--role=\"roles/compute.imageUser\" --condition=None"
        CREATE_REACT_ACCOUNT = \
            "gcloud iam service-accounts create agoge-react-service --display-name \"Agoge React Service Account\""
        ADD_REACT_CLOUD_RUN = \
            "gcloud projects add-iam-policy-binding {project} " \
            "--member=serviceAccount:agoge-react-service@{project}.iam.gserviceaccount.com " \
            "--role=\"roles/run.invoker\""
        ADD_DEFAULT_COMPUTE_SECRETS = ("gcloud projects add-iam-policy-binding {project} "
                                       "--member=serviceAccount:{project_number}-compute@developer.gserviceaccount.com "
                                       "--role=roles/secretmanager.secretAccessor")
        ADD_DEFAULT_COMPUTE_STORAGE = (
            "gcloud projects add-iam-policy-binding {project} "
            "--member=serviceAccount:{project_number}-compute@developer.gserviceaccount.com "
            "--role=roles/storage.admin")
        CREATE_DNS_SERVICE_ACCOUNT = \
            ("gcloud iam service-accounts create agoge-certbot-dns-manager "
             "--display-name \"Agoge Certbot Account for Guac\"")
        ADD_ROLE_DNS_ADMINISTRATOR = (
            "gcloud projects add-iam-policy-binding {project} "
            "--member=serviceAccount:agoge-certbot-dns-manager@{project}.iam.gserviceaccount.com "
            "--role=\"roles/dns.admin\" --condition=None"
        )

    class Authenticate(str, Enum):
        AUTHENTICATE_APPLICATION_DEFAULT = "gcloud auth application-default login " \
                                           "--account=$(gcloud config get-value account)"

    class PubSubTopics(str, Enum):
        CYBER_ARENA = "gcloud pubsub topics create agoge"
        BUDGET = "gcloud pubsub topics create budget"

    class FireStore(str, Enum):
        CHECK_FIRESTORE = "gcloud firestore databases describe --project={project} --database={database}"
        CREATE_FIRESTORE = "gcloud firestore databases create --database={database} --location={region} " \
                           "--type=firestore-native"

    class SharedResourcePermissions(str, Enum):
        # Give a service account permission to launch from every image in the shared resource project
        GRANT_IMAGE_USER = (
            'gcloud projects add-iam-policy-binding {shared_resource_project} '
            '--member="serviceAccount:{dest_sa}" '
            '--role="roles/compute.imageUser"'
        )

    class CreateDefaultVPC(str, Enum):
        CREATE_VPC = "gcloud compute networks create default --subnet-mode=auto"
        INTERNAL_ALLOW = 'gcloud compute firewall-rules create default-allow-internal --network default ' \
                         '--allow="tcp,udp,icmp" --source-ranges 10.128.0.0/9'
        ADMIN_ALLOW = 'gcloud compute firewall-rules create default-allow-management --network default ' \
                      '--allow="tcp:22,tcp:3389,icmp"'


class InstallSettings:
    BULK_SETTINGS_FILENAME = ".bulk_settings.yaml"


class DefaultServerImages(str, Enum):
    WIN_SEC_TOOLS = "image-cyberarena-win-sectools"
    SLIVER_IMPLANT = "image-cyberarena-sliver-implant"
    SLIVER_SERVER = "image-cyberarena-sliver-server"
    LOST_PUPPY = "image-cybergym-lostpuppy"
    LAMP = "image-cyberarena-lamp"
    KALI = "image-kali-linux-2023"
    KALI_DESKTOP = "image-cyberarena-kali-desktop"
    VULN_SSH = "image-vuln-ssh-host"
    WEBGOAT = "image-cyberarena-webgoat-2023"
    METASPLOITABLE = "image-cyberarena-metasploitable3"
    SLINGSHOT = "image-cyberarena-slingshot"
    VULNERABLE_WINDOWS = "image-cyberarena-vulnerable-windows"
    VULNERABLE_UBUNTU = "image-cyberarena-vulnerable-ubuntu"
    CYBERGYM_TEENYWEB = "image-cybergym-teenyweb"
    CSEC1310_POWERSHELL = "image-csec1310-powershell"
    CSEC3300_FINAL = "image-csec3300-final"
    CSEC3314_POWERSHELL = "image-csec3314-powershell"
    CYBERARENA_LAMP = "image-cyberarena-lamp"
    CYBERARENA_SLIVER_IMPLANT = "image-cyberarena-sliver-implant"
    CYBERARENA_WIN_SECTOOLS = "image-cyberarena-win-sectools"
    CYBERGYM_LOSTPUPPY = "image-cybergym-lostpuppy"
    CYBERGYM_NESSUS = "image-cybergym-nessus"
    FORENSICS_WORKSTATION_SZECHUAN = "image-forensics-workstation-szechuan"
    GHOST_CHAIR = "image-ghost-chair"
    KALI_LINUX_2023 = "image-kali-linux-2023"
    AD_DC = "image-cybergym-activedirectory-domaincontroller"
    AD_MEMBER = "image-cybergym-activedirectory-member-server"


def set_google_cloud_service_account_impersonation():
    service_account_email = os.environ.get("GOOGLE_IMPERSONATED_SERVICE_ACCOUNT")
    source_credentials, project = default()

    target_credentials = impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=service_account_email,
        target_scopes=['https://www.googleapis.com/auth/cloud-platform'],
        lifetime=3600
    )
    return target_credentials
