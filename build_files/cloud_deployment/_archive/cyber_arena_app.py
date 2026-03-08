import subprocess
from googleapiclient import discovery

from common.utilities.gcp.cloud_env import CloudEnv


class CyberArenaApp:
    BUILD_FLASK_ASSETS = ["flask", "assets", "build"]
    BUILD_CLOUD_RUN_COMMAND = "gcloud builds submit main_app/ --tag gcr.io/{project}/cyberarena"
    DEPLOY_CLOUD_RUN_COMMAND = "gcloud run deploy cyberarena-v2 --image gcr.io/{project}/cyberarena --memory=4096Mi " \
                               "--cpu 4 --platform=managed --region={region} --allow-unauthenticated " \
                               "--service-account=agoge-service@{project}.iam.gserviceaccount.com"
    # MAP_DNS_COMMAND = "gcloud beta run domain-mappings create --service cyberarena-v2 --domain={dns} --region={region}"
    DEPLOY_CLOUD_FUNCTION_COMMAND = "gcloud functions deploy --quiet cyber-arena-v2 " \
                                    "--region={region} --memory=2048Mi " \
                                    "--entry-point=cyber_arena_cloud_function " \
                                    "--runtime=python311 --source=\"./cloud_functions/\" " \
                                    "--service-account=agoge-service@{project}.iam.gserviceaccount.com " \
                                    "--run-service-account=" \
                                    "projects/{project}/serviceAccounts/{project-number}-compute@developer.gserviceaccount.com " \
                                    "--timeout=540s " \
                                    "--trigger-topic=cyber-arena " \
                                    "--docker-registry=artifact-registry"

    CLOUD_SCHEDULER_NAME = "cyber-arena-hourly-maintenance"
    SCHEDULE = "*/15 * * * *"
    CLOUD_SCHEDULER_COMMAND = f"gcloud scheduler jobs create pubsub {CLOUD_SCHEDULER_NAME} " \
                              f"--schedule=\"{SCHEDULE}\" --topic=cyber-arena --message-body=Hello! " \
                              f"--attributes=handler=MAINTENANCE --location=us-central1"

    def __init__(self, suppress=True):
        self.suppress = suppress
        self.env = CloudEnv()
        self.service = discovery.build('cloudscheduler', 'v1')
        self.job_name = f"projects/{self.env.project}/locations/{self.env.region}/jobs/{self.CLOUD_SCHEDULER_NAME}"

    def deploy_main_app(self):
        print("Compiling assets for Cloud Run application ...")
        process = subprocess.Popen(self.BUILD_FLASK_ASSETS, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, cwd='main_app/')
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(stderr.decode())
            print("Error compiling Flask Assets! See message above. Exiting without updating asset files")
            return False
        print(f"Beginning to package cloud run app. This operation may take a few minutes...")
        command = self.BUILD_CLOUD_RUN_COMMAND.format(project=self.env.project, region=self.env.region)
        ret = subprocess.run(command, capture_output=True, shell=True)
        print(ret.stderr.decode())
        if ret.returncode != 0:
            print(f"Error packaging the Cloud Run App! See messages above. Exiting without deploying the "
                  f"Cloud Run App")
            return False
        command = self.DEPLOY_CLOUD_RUN_COMMAND.format(project=self.env.project, region=self.env.region)
        ret = subprocess.run(command, capture_output=True, shell=True)
        print(ret.stderr.decode())
        if ret.returncode != 0:
            print(f"Error packaging the Cloud Run App! See messages above. Exiting without deploying the "
                  f"Cloud Run App")
            return False
        """
        confirmation = str(input(f"Do you want to map the main app to the DNS record "
                                 f"{self.env.main_app_url}? (y/N): ")).upper() \
            if not self.suppress else "N"
        if confirmation == "N":
            command = self.MAP_DNS_COMMAND.format(dns=self.env.main_app_url, region=self.env.region)
            ret = subprocess.run(command, capture_output=True, shell=True)
            print(ret.stderr.decode())
        """
        return True

    def deploy_cloud_functions(self):
        print(f"Beginning to deploy cloud function. This operation may take a few minutes...")
        command = self.DEPLOY_CLOUD_FUNCTION_COMMAND.format(project=self.env.project, region=self.env.region)
        ret = subprocess.run(command, capture_output=True, shell=True)
        print(ret.stderr.decode())
        if ret.returncode != 0:
            print(f"Error deploying the cloud function! See messages above. Exiting without deploying the "
                  f"cloud function")
            return False
        self._set_scheduler()

    def _set_scheduler(self):
        parent = f'projects/{self.env.project}/locations/{self.env.region}'
        response = self.service.projects().locations().jobs().list(parent=parent).execute()
        job_exists = False
        for job in response.get('jobs', []):
            if job.get('name', None) == self.job_name:
                job_exists = True
        if not job_exists:
            ret = subprocess.run(self.CLOUD_SCHEDULER_COMMAND, capture_output=True, shell=True)
            print(ret.stderr.decode())
            if ret.returncode != 0:
                print(f"Error setting up the cloud scheduler! See messages above.")
