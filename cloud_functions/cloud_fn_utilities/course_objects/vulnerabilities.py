import gzip
import json
import urllib
from datetime import datetime

from common.constants.database import DatabaseTypes, DbOperationTypes, DATABASE_NAME, DbCollections
from common.document_database import DocumentDatabaseFactory
from common.models.agoge import CVEModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames


class Vulnerabilities:
    def __init__(self, env_dict=None):
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.CLOUD_FN
        self.collection = DbCollections.NVD_DATA
        self.env = CloudEnv(env_dict) if env_dict else CloudEnv()
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.db = self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.validator = ModelValidator

    def _check_nvd_collection(self):
        """
        Returns: True if table needs to be created
        """
        query = self.db.query(collection_name=self.collection, limit=1)
        if query and query != []:
            return False
        return True

    def update(self):
        setup_required = self._check_nvd_collection()
        if setup_required:
            self.logger.info(f"{self.class_name}:{self.collection} - Initializing NVD data with current year of "
                             f"vulnerabilities")
            today = datetime.today()
            url = f"https://nvd.nist.gov/feeds/json/cve/1.1/nvdcve-1.1-{today.year}.json.gz"
        else:
            self.logger.info(f"{self.class_name}:{self.collection} - Adding new recent vulnerabilities")
            url = "https://nvd.nist.gov/feeds/json/cve/1.1/nvdcve-1.1-recent.json.gz"
        local_filename = urllib.request.urlretrieve(url)
        json_feed = json.loads(gzip.open(local_filename[0]).read())
        self.logger.debug(f"{self.class_name}:{self.collection} - Processing {local_filename}")
        cve_list = []
        for cve in json_feed['CVE_Items']:
            try:
                if config := next(iter(cve['configurations']['nodes']), None):
                    if cpe := next(iter(config['cpe_match']), None):
                        cpe_parts = cpe['cpe23Uri'].split(':')
                        cvss = cve["impact"]["baseMetricV3"]["cvssV3"]
                        cve_dict = {
                            'cve_id': cve["cve"]["CVE_data_meta"]["ID"],
                            'vendor': cpe_parts[3],
                            'product': cpe_parts[4],
                            'attack_vector': cvss["attackVector"],
                            'complexity': cvss["attackComplexity"],
                            'priv': cvss["privilegesRequired"],
                            'ui': cvss["userInteraction"],
                            'confidentiality': cvss["confidentialityImpact"],
                            'integrity': cvss["integrityImpact"],
                            'availability': cvss["availabilityImpact"],
                            'description': str(cve["cve"]["description"]["description_data"][0]["value"]),
                        }
                        # Convert dict to Entity and append to cve_list
                        model = (
                            self.validator(model=CVEModel, log_location=self.log_name)
                            .load(data=cve_dict, as_dict=False, halt_on_error=False)
                        )
                        if model:
                            cve_list.append(
                                self.db.operation(
                                    collection_name=self.collection,
                                    doc_id=model.cve_id,
                                    operation_type=DbOperationTypes.SET,
                                    data=model.model_dump()
                                )
                            )
            except KeyError:
                pass

        # Update the table with the new cve list
        self.db.batch_write(cve_list)

# [ eof ]
