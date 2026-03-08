import zoneinfo

from datetime import datetime, timedelta, UTC
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from cloud_fn_utilities.periodic_maintenance.hourly_maintenance import HourlyMaintenance
from cloud_fn_utilities.periodic_maintenance.quarter_hourly_maintenance import QuarterHourlyMaintenance
from cloud_fn_utilities.periodic_maintenance.daily_maintenance import DailyMaintenance


class MaintenanceHandler:
    def __init__(
        self,
        debug: bool = False,
        env_dict: dict = None
    ) -> None:
        self.class_name = self.__class__.__name__
        self.debug = debug
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.class_name)
        now = self._get_localized_time()
        self.daily = self.hourly = self.quarter_hourly = False

        if self._is_midnight(now):
            self.daily = True
            self.hourly = True
            self.quarter_hourly = True
        elif 12 <= now.minute <= 18:
            self.hourly = True
            self.quarter_hourly = True
        elif (27 <= now.minute <= 33) or (42 <= now.minute <= 48):
            self.quarter_hourly = True

        self.logger.info(f'{self.class_name} - Maintenance called at {now} for timezone {self._get_timezone()}')

    def route(self):
        self.logger.debug(f'{self.class_name}:(DAILY, HOURLY, QUARTER HOURLY) - '
                          f'{self.daily} : {self.hourly} : {self.quarter_hourly}')
        if self.quarter_hourly:
            self.logger.info(f"{self.class_name} - Running quarter hourly maintenance tasks")
            QuarterHourlyMaintenance(env_dict=self.env_dict, debug=self.debug).run()

        if self.hourly:
            self.logger.info(f"{self.class_name} - Running hourly maintenance tasks")
            HourlyMaintenance(env_dict=self.env_dict, debug=self.debug).run()

        if self.daily:
            self.logger.info(f"{self.class_name} - Running daily maintenance tasks")
            DailyMaintenance(env_dict=self.env_dict, debug=self.debug).run()

    def _is_midnight(self, now):
        midnight = datetime(now.year, now.month, now.day, 0, 0, tzinfo=self._get_timezone())
        start = midnight - timedelta(minutes=5)
        end = midnight + timedelta(minutes=15)
        if start <= now <= end:
            return True
        return False

    def _get_localized_time(self):
        now = datetime.now(UTC)
        timezone = self._get_timezone()
        return now.astimezone(timezone)

    def _get_timezone(self):
        return zoneinfo.ZoneInfo(self.env.timezone)
