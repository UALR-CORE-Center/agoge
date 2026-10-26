"""Seed a managed WireGuard Community Lab into the selected site's catalog."""
import re
import time

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.constants.states import ImageStatus
from common.document_database.factory import DocumentDatabaseFactory
from common.exceptions import BadRequest, Conflict
from common.models.agoge import CatalogModel, UnitModel
from common.services.wireguard_lab_spec import configure_kit_topology, default_wireguard_spec
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.compute.compute_image import ComputeImageAPI
from common.utilities.gcp.compute.image_ownership import image_source


class WireGuardLabTemplate:
    DEFAULT_ID = 'wireguard-factory-lab'

    def __init__(self, project: str):
        self.project = project

    @staticmethod
    def _connections(record: dict) -> list:
        connections = record.get('human_interaction') or []
        if isinstance(connections, dict):
            connections = [connections]
        if record.get('status') != ImageStatus.CHECKED_IN.value or record.get('image_exists') is False:
            return []
        return [item for item in connections if isinstance(item, dict) and item.get('display')
                and item.get('username') and item.get('password')
                and item.get('protocol') in ('ssh', 'rdp', 'vnc')]

    def run(self) -> bool:
        print(f'Upload destination: {self.project}/{DATABASE_NAME}/catalog.')
        print('This uploads a reusable template; it does not build VMs or assign a factory kit.')
        try:
            env = CloudEnv(project=self.project)
            if env.project != self.project:
                raise BadRequest('The selected project differs from its environment document')
            self.db = DocumentDatabaseFactory.create_db_object(
                db_type=DatabaseTypes.firestore, project_id=self.project, database_name=DATABASE_NAME)
            records = self.db.query(collection_name=DbCollections.IMAGE) or []
            candidates = {record['name']: record for record in records
                          if isinstance(record.get('name'), str) and self._connections(record)}
            if not candidates:
                raise BadRequest('No checked-in student image has a password-based display connection. '
                                 'Import/check in a Kali image in Server Manager first.')
            print('Available registered student templates (GCP AMD64/READY is checked after selection):')
            for identifier in sorted(candidates):
                print(f'  {identifier}')
            default_image = next((identifier for identifier, record in sorted(candidates.items())
                                  if identifier in ('kali-linux-2023', 'image-kali-linux-2023')
                                  or record.get('image') == 'image-kali-linux-2023'), '')
            hint = f' [{default_image}]' if default_image else ''
            image_id = input(f'Registered student image template ID{hint}: ').strip() or default_image
            if image_id not in candidates:
                raise BadRequest('Choose one of the registered student template IDs listed above')
            email = input(f'Instructor email [{env.get_env().get("admin_email") or ""}]: ').strip()
            email = email or env.get_env().get('admin_email') or ''
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
                raise BadRequest('Enter the instructor email used to sign in to this Agoge site')
            catalog_id = input(f'Catalog document ID [{self.DEFAULT_ID}]: ').strip() or self.DEFAULT_ID
            if not re.fullmatch(r'[a-z][a-z0-9-]{0,51}', catalog_id):
                raise BadRequest('Catalog ID must be 1–52 lowercase letters, digits, or hyphens, starting with a letter')
            source = self._student_source(candidates[image_id], image_id, env.get_env())
            catalog = self._catalog(catalog_id, source, self._connections(candidates[image_id]),
                                    email, int(env.get_env().get('wireguard_port') or 51820))
            created = self._save_new_or_identical(catalog)
            destination = f'{self.project}/{DATABASE_NAME}/catalog/{catalog_id}'
            print(f'{"Uploaded" if created else "Already current"}: {destination}')
            print('In this site, open Teachers → New Lab, refresh the Lab Catalog, select '
                  'WireGuard Factory Lab, and click Build Lab.')
            print('Select an enrolled authorized kit, student capacity, and expiration, then submit the build.')
            return True
        except (BadRequest, Conflict) as error:
            print(f'WireGuard template upload did not finish: {error.message}')
        except Exception as error:
            # SDK/validation error bodies can include image connection passwords.
            print(f'WireGuard template upload did not finish ({type(error).__name__}). '
                  'Check setup credentials, selected-project Firestore write/transaction access, '
                  'and GCP image read access. No existing catalog template was replaced.')
        return False

    def _student_source(self, record: dict, identifier: str, env: dict) -> str:
        reference = image_source(record)
        explicit = re.search(r'(?:^|/)projects/([^/]+)/global/images/([^/]+)$', reference)
        resource = explicit.group(2) if explicit else record.get('image') or identifier
        if not isinstance(resource, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,62}', resource):
            raise BadRequest('The selected student template needs a concrete checked-in GCP image source')
        image = ComputeImageAPI(self.project, env['region'], env['zone']).get(
            resource=resource, project=explicit.group(1) if explicit else self.project,
            fallback_to_shared=not bool(explicit))
        if str(image.status).upper() != 'READY' or str(image.architecture).upper() != 'X86_64':
            raise BadRequest('The selected student boot image must be READY and AMD64 for E2')
        return image.self_link

    @staticmethod
    def _catalog(identifier: str, source: str, connections: list, instructor: str, port: int) -> dict:
        unit = UnitModel(id=identifier, instructor_id=[instructor],
                         **default_wireguard_spec(source, connections))
        # A catalog is deliberately unassigned. The placeholder equipment route
        # is replaced from the authorized registered kit on every Unit build.
        configure_kit_topology(unit, '172.30.0.0/24', port)
        unit.summary.description += (' Build with an enrolled factory kit; its equipment network and '
                                     'WireGuard settings are assigned automatically. One Kali/workstation per student.')
        return CatalogModel.model_validate({**unit.model_dump(), 'discriminator': 'wireguard-starter'}).model_dump()

    def _save_new_or_identical(self, catalog: dict) -> bool:
        document = self.db.db.collection(DbCollections.CATALOG.value).document(catalog['id'])

        def save(transaction):
            snapshot = document.get(transaction=transaction)
            if snapshot.exists:
                existing = snapshot.to_dict()
                # Timestamps do not make an otherwise identical starter a change.
                normalize = lambda value: {key: item for key, item in value.items() if key != 'creation_timestamp'}
                if normalize(existing) == normalize(catalog):
                    return False
                raise Conflict('This catalog ID already contains a different template. '
                               'Keep it and rerun with another catalog document ID.')
            transaction.set(document, {**catalog, 'creation_timestamp': time.time()})
            return True

        return self.db.transaction(save)
