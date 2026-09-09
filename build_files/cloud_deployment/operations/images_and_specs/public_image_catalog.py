"""Populate a selected child's public OS catalog from the setup command line."""

from cloud_functions.cloud_fn_utilities.course_objects.compute.google_image_sync_manager import GoogleImageSyncManager
from common.utilities.gcp.cloud_env import CloudEnv


class PublicImageCatalog:
    def __init__(self, project: str):
        self.project = project

    def run(self) -> bool:
        print(f'Synchronizing public OS image families into {self.project}/agoge-v1/google-images.')
        print('This can take a few minutes. Publisher results and errors appear in this terminal.')
        try:
            env = CloudEnv(project=self.project)
            if env.project != self.project:
                raise ValueError('The selected project differs from its environment document.')
            report = GoogleImageSyncManager(env=env.get_env()).sync()
        except Exception as error:
            print(f'Public OS image synchronization did not finish: {error}')
            print('Check the reported publisher or database error, refresh setup credentials if needed, '
                  'then retry Server Images & Build Specs → Synchronize Public OS Images.')
            return False

        for publisher, count in sorted(report['project_counts'].items()):
            print(f'  {publisher}: {count} image families refreshed')
        print(f'{report["image_count"]} public image families refreshed; '
              f'{report["enabled_count"]} enabled among them.')
        print('Reload Machine Configuration → Server Image. Use Admin → Image Manager to enable additional families.')
        if report['failed_projects']:
            for publisher, error in report['failed_projects'].items():
                print(f'  Could not refresh {publisher}: {error}')
            print('Available publishers were saved and failed publishers kept their previous records. '
                  'Resolve the errors and rerun this operation to finish.')
            return False
        return True
