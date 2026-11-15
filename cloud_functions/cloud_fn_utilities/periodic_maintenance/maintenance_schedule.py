"""The local-time window used by Agoge's daily Pub/Sub maintenance."""

from datetime import datetime, timedelta


def is_daily_maintenance_time(now: datetime) -> bool:
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(minutes=5) <= now <= midnight + timedelta(minutes=15)
