from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.constants.pub_sub import PubSub

from cloud_fn_utilities.reports.attack_report import AttackReport


class ReportHandler:
    def __init__(self, event_attributes, env_dict=None):
        self.class_name = self.__class__.__name__
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.class_name)
        self.event_attributes = event_attributes
        self.report_type = self.event_attributes.get('report_type', None)
        if not self.report_type:
            raise AttributeError('Missing attr report_type in request')

    def route(self):
        if self.report_type == PubSub.Reports.ATTACK:
            AttackReport(self.event_attributes)

# [ eof ]
