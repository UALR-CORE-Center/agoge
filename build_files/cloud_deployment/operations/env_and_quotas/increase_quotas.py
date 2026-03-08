# requirements.txt
# google-cloud-cloudquotas>=0.1.18  (plus whatever else you already use)

import uuid
from typing import Dict, List, Tuple

from google.api_core.exceptions import InvalidArgument
from google.cloud import cloudquotas_v1
from google.cloud.cloudquotas_v1.types import QuotaPreference, QuotaConfig

from common.utilities.gcp.cloud_env import CloudEnv


class QuotaManager:
    """
    Adjusts project-level quotas with Cloud Quotas API instead of filing support
    tickets.  You must enable the API and grant the caller
    `roles/cloudquotas.admin` on the project first.
    """

    #: (service, metric, region, preferred_value)
    _REQUESTS: List[Tuple[str, str, str, int]] = [
        # Compute Engine – regional quotas
        ("compute.googleapis.com", "NETWORKS-per-project", "global", 100),
        ("compute.googleapis.com", "FIREWALLS-per-project", "global", 500),
        ("compute.googleapis.com", "ROUTES-per-project", "global",      600),
        ("compute.googleapis.com", "IN-USE-ADDRESSES-per-project-region", "us-central1", 100),
        ("compute.googleapis.com", "CPUS-per-project-region", "us-central1", 900),
    ]

    def __init__(self, project: str, tz: str = "America/Chicago", env_dict: Dict | None = None):
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.timezone = tz
        self.contact_email = input(
            "Email Google Support can contact if they have questions: "
        ).strip() or self.env.admin_email

        self.client = cloudquotas_v1.CloudQuotasClient()

        # Parent is always {project}/locations/globalfor project-level quotas
        self.project_str = f"projects/{project}/locations/global"

    # ---------- public API -------------------------------------------------

    def request_all(self) -> None:
        for service, metric_id, region, limit in self._REQUESTS:
            quota_info = self._lookup_quota_info(service, metric_id)
            if not quota_info:
                print(f"⚠️  {metric_id} not found in Cloud Quotas; skipping.")
                continue

            qp = self._build_quota_preference(quota_info, region, limit)
            try:
                response = self.client.create_quota_preference(
                    parent=self.project_str,
                    quota_preference=qp,
                    # Let the server pick an ID; you can also set quota_preference_id
                )
                print(f"✅ Requested {metric_id} → {limit}. "
                      f"Resource: {response.name}")
            except InvalidArgument as exc:
                print(f"Request for {metric_id} already exists, skipping.")

    # ---------- helpers ----------------------------------------------------

    def _lookup_quota_info(self, service: str, quota_id: str):
        """
        Return the QuotaInfo whose quota_id matches `quota_id` for `service`.
        """
        parent = f"{self.project_str}/services/{service}"
        quota_list = self.client.list_quota_infos(parent=parent)
        for qi in quota_list:
            if qi.quota_id == quota_id:
                return qi
        return None

    def _build_quota_preference(
        self,
        quota_info,
        region: str,
        preferred_value: int,
    ) -> QuotaPreference:
        """Compose the QuotaPreference request body."""
        dimensions = {}
        if region.lower() != "global":
            dimensions["region"] = region

        return QuotaPreference(
            service=quota_info.service,
            quota_id=quota_info.quota_id,
            dimensions=dimensions,
            justification=(
                "Higher limit required for upcoming workload spikes "
                "and student lab environments."
            ),
            contact_email=self.contact_email,
            quota_config=QuotaConfig(preferred_value=preferred_value),
        )
