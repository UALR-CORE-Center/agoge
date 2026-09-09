"""Maintain setup menu labels without changing tenant or GCP project identities."""

from collections import Counter

from common.constants.build_constants import BuildConstants
from common.constants.database import DATABASE_NAME, DbCollections, DatabaseTypes
from common.document_database.factory import DocumentDatabaseFactory
from common.exceptions import AgogeValidationError


class ProjectMenu:
    def __init__(self):
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            project_id=BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT,
        )

    def configurations(self) -> dict:
        records = self.db.query(collection_name=DbCollections.PROJECT_INFO)
        visible = [record for record in records if not record.get('setup_menu_hidden', False)]
        labels = [self._label(record) for record in visible]
        counts = Counter(label.casefold() for label in labels)
        projects = {}
        for record, label in zip(visible, labels):
            project_id = record['project_name']
            if counts[label.casefold()] > 1:
                label = f'{label} [{project_id}]'
            if label in projects:
                raise AgogeValidationError('Conflicting project menu labels. Rename entries by project ID.')
            projects[label] = {
                'impersonation_account': record['impersonation_account'],
                'project_id': project_id,
            }
        return projects

    @staticmethod
    def _label(record) -> str:
        return record.get('setup_menu_name') or record['tenant_name']

    @classmethod
    def _resolve(cls, records, selector) -> dict:
        # IDs take precedence. A label must identify exactly one project,
        # including hidden entries, so repeated commands remain safe.
        matches = [record for record in records if record['project_name'] == selector]
        if not matches:
            matches = [
                record for record in records
                if selector.casefold() in {cls._label(record).casefold(), record['tenant_name'].casefold()}
            ]
        if len(matches) != 1:
            raise AgogeValidationError(
                f'Environment {selector!r} matched {len(matches)} records. '
                'Use an exact project ID or a unique name.'
            )
        return matches[0]

    def update(self, *, hide=(), show=(), rename=()) -> None:
        records = self.db.query(collection_name=DbCollections.PROJECT_INFO)
        patches = {}
        for selector, hidden in [(name, True) for name in hide] + [(name, False) for name in show]:
            record = self._resolve(records, selector)
            patch = patches.setdefault(record['project_name'], {})
            if 'setup_menu_hidden' in patch and patch['setup_menu_hidden'] != hidden:
                raise AgogeValidationError('An environment cannot be both hidden and shown in one command.')
            patch['setup_menu_hidden'] = hidden
        for selector, label in rename:
            label = label.strip()
            if not label or len(label) > 100 or any(ord(char) < 32 for char in label):
                raise AgogeValidationError('Menu names must contain 1 to 100 printable characters.')
            record = self._resolve(records, selector)
            patch = patches.setdefault(record['project_name'], {})
            if 'setup_menu_name' in patch and patch['setup_menu_name'] != label:
                raise AgogeValidationError('Specify only one new name per environment.')
            patch['setup_menu_name'] = label

        # Validate document IDs and all selectors before making any changes.
        # These records are keyed by project ID in the shared registry.
        changes = []
        for project_id, patch in patches.items():
            current = self.db.get(collection_name=DbCollections.PROJECT_INFO, doc_id=project_id)
            if not current or current.get('project_name') != project_id:
                raise AgogeValidationError(f'No matching project-info/{project_id} document. No menu changes made.')
            patch = {key: value for key, value in patch.items() if current.get(key) != value}
            if patch:
                changes.append((project_id, patch))
        for project_id, patch in changes:
            self.db.update(collection_name=DbCollections.PROJECT_INFO, doc_id=project_id, data=patch)
            print(f'Updated setup menu for {project_id}: {patch}')
        if not changes:
            print('The requested setup menu settings are already applied.')
