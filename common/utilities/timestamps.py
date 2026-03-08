import math
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo


class Timestamps:
    @classmethod
    def from_utc_str(
        cls,
        datetime_str: str
    ) -> float:
        return (datetime.fromisoformat(datetime_str)).timestamp()

    @classmethod
    def get_current_timestamp_utc(
        cls,
        add_seconds: int = 0,
        round_to_quarter: bool = False
    ) -> float:
        # Ensure add_seconds is an integer; if not, default to 0
        try:
            add_seconds = add_seconds if isinstance(add_seconds, int) else int(add_seconds)
        except ValueError:
            add_seconds = 0
        timestamp = (datetime.now(timezone.utc) + timedelta(seconds=add_seconds)).timestamp()
        if round_to_quarter:
            return cls.round_to_next_quarter(timestamp)
        return timestamp

    @classmethod
    def get_utc_timestamp_from_datetime(
        cls,
        datetime_str: str,
        tz: str
    ) -> float:
        try:
            # Parse the datetime string into a datetime object
            datetime_str = datetime_str.split('.')[0]
            local_dt = datetime.strptime(datetime_str.replace("T", " "), "%Y-%m-%d %H:%M:%S")
            local_dt = local_dt.replace(tzinfo=ZoneInfo(tz))

            # Convert to UTC and return the timestamp
            return local_dt.astimezone(ZoneInfo("UTC")).timestamp()
        except ValueError as e:
            raise ValueError(f'Error converting datetime: {e}')

    @classmethod
    def get_historic_utc_timestamp(
        cls,
        days: int = 0
    ) -> float:
        return (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()

    @classmethod
    def round_to_next_quarter(
        cls,
        timestamp: float
    ) -> float:
        return math.ceil(timestamp / 900) * 900
