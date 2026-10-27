"""Built-in instructor flow without requiring a hand-authored catalog spec."""
import re
from datetime import datetime, timezone

from common.constants.database import DbCollections
from common.exceptions import BadRequest
from common.utilities.gcp.compute.compute_image import ComputeImageAPI
from common.utilities.gcp.compute.image_ownership import image_source
from common.services.wireguard_lab_spec import DEFAULT_STUDENT_IMAGE, default_wireguard_spec
from common.services.student_image_profile import student_image_profile
from common.services.wireguard_provisioning import WireGuardProvisioningService, resolve_remote_peer_id
from core.unit import Unit


class WireGuardLab:
    def __init__(self, env_dict: dict):
        self.env_dict = env_dict

    def build(self, requester, data: dict) -> str:
        if not requester.is_authorized:
            raise BadRequest("An instructor account is required")
        kit_id = resolve_remote_peer_id(data)
        WireGuardProvisioningService(self.env_dict).get_authorized_kit(kit_id, requester)
        count = data.get("build_count", 1)
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 100:
            raise BadRequest("Choose between 1 and 100 student workstations")
        try:
            expiry = datetime.fromisoformat(str(data.get("expires", "")).replace("Z", "+00:00"))
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry <= datetime.now(timezone.utc):
                raise ValueError
        except ValueError:
            raise BadRequest("Choose a future expiration date") from None
        image_name = data.get("student_image") or DEFAULT_STUDENT_IMAGE
        if not isinstance(image_name, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,62}", image_name):
            raise BadRequest("Choose a registered student server image")
        manager = Unit(self.env_dict)
        image = manager.db.get(collection_name=DbCollections.IMAGE, doc_id=image_name)
        if not image:
            raise BadRequest(f"Student image '{image_name}' is unavailable. Register a Windows or Linux student image in Server Manager first.")
        connections, reasons = student_image_profile({**image, 'name': image_name}, self.env_dict['project'])
        if reasons:
            raise BadRequest('Student image is not eligible: ' + '; '.join(reasons))
        try:
            reference = image_source(image)
            explicit = re.search(r'(?:^|/)projects/([^/]+)/global/images/([^/]+)$', reference)
            resource = explicit.group(2) if explicit else image.get('image') or image_name
            if not re.fullmatch(r'[a-z][a-z0-9-]{0,62}', resource):
                raise ValueError('The registered image has no concrete boot source')
            source = ComputeImageAPI(project=self.env_dict['project'], region=self.env_dict['region'],
                                     zone=self.env_dict['zone']).get(
                resource=resource, project=explicit.group(1) if explicit else self.env_dict['project'],
                fallback_to_shared=True)
        except Exception:
            raise BadRequest('The student boot image cannot be read in GCP; check its image name and runtime access') from None
        if str(source.status).upper() != 'READY' or str(source.architecture).upper() != 'X86_64':
            raise BadRequest('The student image must be a ready AMD64 image for the E2 workstations')
        build_data = {**data, "build_file": "builtin-wireguard-factory",
                      "expires": expiry.isoformat(), "build_count": count}
        return manager.build(requester=requester, data=build_data,
            catalog_override=default_wireguard_spec(source.self_link, connections))
