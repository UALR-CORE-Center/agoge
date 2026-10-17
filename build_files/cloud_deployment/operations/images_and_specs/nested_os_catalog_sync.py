"""Seed a selected child's nested guest OS catalog from common/data/nested_os_catalog.json (PRD V6)."""
import json
from pathlib import Path
from typing import List

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections, DbOperationTypes
from common.document_database import DocumentDatabaseFactory
from common.models.agoge import NestedOsCatalogModel
from common.utilities.gcp.cloud_env import CloudEnv

CATALOG_JSON = Path(__file__).resolve().parents[4] / 'common' / 'data' / 'nested_os_catalog.json'


class NestedOsCatalogSync:
    def __init__(self, project: str, db=None, catalog_path: Path = CATALOG_JSON):
        self.project = project
        self._db = db
        self.catalog_path = catalog_path

    def run(self) -> bool:
        print(f'Synchronizing the nested guest OS catalog into {self.project}/{DATABASE_NAME}/'
              f'{DbCollections.NESTED_OS_CATALOG}.')
        try:
            env = CloudEnv(project=self.project)
            if env.project != self.project:
                raise ValueError('The selected project differs from its environment document.')
            report = self.sync()
        except Exception as error:
            print(f'The nested guest OS catalog was not synchronized: {error}')
            print('Check the error, refresh setup credentials if needed, then rerun '
                  'Server Images & Build Specs → Synchronize Nested Guest OS Catalog.')
            return False
        print(f'{report["added"]} entries added, {report["updated"]} updated, {report["unchanged"]} unchanged.')
        print('Administrators can disable an entry by setting is_enabled to false; later syncs keep that choice.')
        return True

    def sync(self) -> dict:
        """Upsert every seeded entry by id. Only changed entries are written, so a second sync writes nothing."""
        entries = self.load_entries(self.catalog_path)
        db = self.db
        existing = {record.get('id'): record for record in db.query(collection_name=DbCollections.NESTED_OS_CATALOG) or []}
        operations, report = [], {'added': 0, 'updated': 0, 'unchanged': 0}
        for entry in entries:
            data = entry.model_dump()
            previous = existing.get(entry.id)
            # An administrator's enable/disable choice outlives the seed; everything else follows the JSON.
            if previous is not None and isinstance(previous.get('is_enabled'), bool):
                data['is_enabled'] = previous['is_enabled']
            if previous == data:
                report['unchanged'] += 1
                continue
            report['added' if previous is None else 'updated'] += 1
            operations.append(db.operation(collection_name=DbCollections.NESTED_OS_CATALOG, doc_id=entry.id,
                                           operation_type=DbOperationTypes.SET, data=data))
        # Entries missing from the JSON are left alone: an administrator may have added their own.
        if operations:
            db.batch_write(operations)
        return report

    @staticmethod
    def load_entries(path: Path) -> List[NestedOsCatalogModel]:
        entries = [NestedOsCatalogModel(**item) for item in json.loads(path.read_text())]
        ids = [entry.id for entry in entries]
        duplicates = sorted({entry_id for entry_id in ids if ids.count(entry_id) > 1})
        if duplicates:
            raise ValueError(f'{path.name} repeats catalog ids: {", ".join(duplicates)}')
        return entries

    @property
    def db(self):
        if self._db is None:
            self._db = DocumentDatabaseFactory.create_db_object(
                db_type=DatabaseTypes.firestore, database_name=DATABASE_NAME, project_id=self.project,
            )
        return self._db
