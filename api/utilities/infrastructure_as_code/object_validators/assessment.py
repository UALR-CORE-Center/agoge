from common.exceptions import AgogeValidationError
from common.models.agoge import AssessmentModel
from common.utilities.gcp.bucket_manager import BucketManager
from common.utilities.gcp.cloud_logger import LoggerNames


class AssessmentValidator:
    def __init__(
        self,
        config: dict
    ) -> None:
        self.config = config
        self.bucket_manager = BucketManager(log_name=LoggerNames.API)

    def load(self) -> dict:
        config = self.config
        server_names = [server['name'] for server in config.get('servers', [])]
        script_names = self.bucket_manager.get_scripts()

        assessment = config.get('assessment')
        assessment_script = config.get('assessment_script')

        if assessment_server := assessment.get('server'):
            if assessment_server not in server_names:
                raise AgogeValidationError(
                    f"Invalid Server: Assessment uses a script on the server '{assessment_server}' "
                    f"that does not exist in the specification"
                )

        if assessment_script:
            script_name = assessment_script.get('script')
            if script_name not in script_names:
                raise AgogeValidationError(
                    f"Invalid Script: Assessment uses the script '{script_name}' "
                    f"that does not exist in the cloud bucket for startup scripts"
                )

            script_server = assessment_script.get('server')
            if script_server:
                server_details = next(
                    (
                        server
                        for server in config.get('servers', [])
                        if server['name'] == script_server
                    ), None
                )
                if server_details:
                    assessment_script['operating_system'] = server_details['details']['os']

        # Validate final model
        AssessmentModel(**assessment)
        return config
