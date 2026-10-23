"""Seed a managed WireGuard Community Lab into the selected site's catalog."""
import re
import time
import json

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.constants.build_constants import BuildConstants
from common.document_database.factory import DocumentDatabaseFactory
from common.exceptions import BadRequest, Conflict, NotFound
from common.models.agoge import CatalogModel, UnitModel
from common.services.wireguard_lab_spec import configure_kit_topology, default_wireguard_spec
from common.services.student_image_profile import student_image_profile
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.compute.compute_image import ComputeImageAPI
from common.utilities.gcp.compute.image_ownership import image_source


class WireGuardLabTemplate:
    DEFAULT_ID = 'wireguard-factory-lab'

    def __init__(self, project: str):
        self.project = project

    @staticmethod
    def _connections(record: dict, project: str | None = None) -> list:
        return student_image_profile(record, project)[0]

    def run(self) -> bool:
        print(f'Upload destination: {self.project}/{DATABASE_NAME}/catalog.')
        print('This uploads a reusable template; it does not build VMs or assign a remote peer.')
        try:
            env = CloudEnv(project=self.project)
            if env.project != self.project:
                raise BadRequest('The selected project differs from its environment document')
            self.db = DocumentDatabaseFactory.create_db_object(
                db_type=DatabaseTypes.firestore, project_id=self.project, database_name=DATABASE_NAME)
            records = self.db.query(collection_name=DbCollections.IMAGE) or []
            candidates = {}
            print('Student image eligibility (credential values are not shown):')
            for index, record in enumerate(records, 1):
                connections, reasons = student_image_profile(record, self.project)
                name = record.get('name')
                label = name if isinstance(name, str) and name.strip() else f'<unnamed image {index}>'
                # Escape newlines/control characters; never print whole records.
                label = json.dumps(label[:120], ensure_ascii=True)
                if reasons:
                    print(f'  {label}: excluded - {"; ".join(reasons)}')
                else:
                    candidates[record['name']] = record
                    print(f'  {label}: eligible (GCP source checked after selection)')
            if not candidates:
                raise BadRequest('No student image passed the checks listed above. '
                                 'Use a checked-in Windows or Linux image with an enabled password-based '
                                 'RDP, SSH, or VNC display connection. No Kali image name is required.')
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
            catalog = self._catalog(catalog_id, source, self._connections(candidates[image_id], self.project),
                                    email, int(env.get_env().get('wireguard_port') or 51820))
            created = self._save_new_or_identical(catalog)
            destination = f'{self.project}/{DATABASE_NAME}/catalog/{catalog_id}'
            print(f'{"Uploaded" if created else "Already current"}: {destination}')
            print('In this site, open Teachers → New Lab, refresh the Lab Catalog, select '
                  'WireGuard Remote Lab, and click Build Lab.')
            print('Select an authorized remote peer, student capacity, and expiration, then submit the build.')
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
        source_project = explicit.group(1) if explicit else self.project
        if not re.fullmatch(r'[a-z0-9][a-z0-9.:-]{0,252}', source_project):
            raise BadRequest('The selected student template has an invalid GCP source project')
        print(f'Validating student Compute image: projects/{source_project}/global/images/{resource}')
        image_api = ComputeImageAPI(self.project, env['region'], env['zone'])
        try:
            image = image_api.get(
                resource=resource, project=source_project, fallback_to_shared=not bool(explicit))
        except NotFound:
            projects = [source_project]
            shared_project = BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT
            if not explicit and shared_project not in projects:
                projects.append(shared_project)
            sources = ', '.join(f'projects/{project}/global/images/{resource}' for project in projects)
            checks = '\n'.join(
                f'  gcloud compute images describe {resource} --project={project} '
                '--format="yaml(name,status,architecture,selfLink)"' for project in projects)
            print(
                f'The selected student Compute image was not found: {sources}.\n'
                f'Verify with the same account selected in setup:\n{checks}\n'
                'Copying a Firestore image record does not copy its Compute image.')
            recover = input('Choose an existing GCP image for this catalog upload instead? [y/N]: ')
            if recover.strip().lower() not in ('y', 'yes'):
                raise BadRequest(
                    'Correct the selected image record\'s source reference (self_link, image, or boot disk '
                    'initializeParams.sourceImage) to the existing published image, or import/check in '
                    'a student image first. Confirm image read access if the source is correct. '
                    'No catalog template was written.') from None
            image = self._choose_student_source(image_api)
        if str(image.status).upper() != 'READY' or str(image.architecture).upper() != 'X86_64':
            raise BadRequest('The selected student boot image must be READY and AMD64 for E2')
        print(f'Student boot source for this catalog: {image.self_link}')
        return image.self_link

    @staticmethod
    def _choose_student_source(image_api):
        """Choose a verified source for this catalog without editing image records."""
        default_project = BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT
        print('Student connection settings will come from the selected Agoge template. '
              'Choose an image that accepts its saved username/password and connection protocol.')
        while True:
            value = input(f'Source GCP project or full image reference [{default_project}] '
                          '(cancel to stop): ').strip() or default_project
            if value.lower() == 'cancel':
                raise BadRequest('Image selection canceled. No catalog template was written.')
            explicit = re.search(r'(?:^|/)projects/([^/]+)/global/images/([a-z][a-z0-9-]{0,62})$', value)
            project = explicit.group(1) if explicit else value
            if not re.fullmatch(r'[a-z0-9][a-z0-9.:-]{0,252}', project):
                print('Enter a GCP project ID or a concrete projects/PROJECT/global/images/IMAGE reference.')
                continue
            if explicit:
                resource = explicit.group(2)
            else:
                try:
                    images = image_api.list(project=project)
                except Exception as error:
                    print(f'Could not list images in {project} ({type(error).__name__}). '
                          'Check image list access, enter another project, or paste an exact image reference.')
                    continue
                names = sorted({
                    image.name for image in images
                    if str(image.status).upper() == 'READY' and str(image.architecture).upper() == 'X86_64'
                    and re.fullmatch(r'[a-z][a-z0-9-]{0,62}', image.name)
                })
                if not names:
                    print(f'No READY AMD64 images found in {project}. Choose another source project or cancel.')
                    continue
                print(f'Available READY AMD64 images in {project}:')
                numbered_names = {str(index): name for index, name in enumerate(names, 1)}
                for index, name in numbered_names.items():
                    print(f'  {index}. {name}')
                while True:
                    resource = input('GCP image number or exact name '
                                     '(Enter for another project, cancel to stop): ').strip()
                    if resource.lower() == 'cancel':
                        raise BadRequest('Image selection canceled. No catalog template was written.')
                    if not resource:
                        break
                    resource = numbered_names.get(resource, resource)
                    if resource in names:
                        break
                    print('Choose an image from the numbered list.')
                if not resource:
                    continue
            try:
                # Re-read the selected image and never substitute a different project.
                return image_api.get(resource=resource, project=project, fallback_to_shared=False)
            except NotFound:
                print(f'Image projects/{project}/global/images/{resource} was not found. '
                      'Choose another source project or image reference.')

    @staticmethod
    def _catalog(identifier: str, source: str, connections: list, instructor: str, port: int) -> dict:
        unit = UnitModel(id=identifier, instructor_id=[instructor],
                         **default_wireguard_spec(source, connections))
        # A catalog is deliberately unassigned. The placeholder equipment route
        # is replaced from the authorized remote peer's private LAN on every Unit build.
        configure_kit_topology(unit, '172.30.0.0/24', port)
        unit.summary.description += (' Build with a registered remote peer; its private LAN and '
                                     'WireGuard settings are assigned automatically. One workstation per student.')
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
