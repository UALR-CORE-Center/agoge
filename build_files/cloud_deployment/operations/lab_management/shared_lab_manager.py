import subprocess
from typing import List, Dict, Callable, Set

from google.api_core.exceptions import NotFound

from common.document_database.factory import DocumentDatabaseFactory, DocumentDatabase
from common.constants.database import DatabaseTypes, DATABASE_NAME, DbCollections
from cloud_deployment.utilities.globals import ShellCommands
from cloud_deployment.operations.env_and_quotas.gcloud_environment_manager import (
    GcloudEnvironmentManager,
)

CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
NC = "\033[0m"


class SharedLabManager:
    """
    A two-way, menu-driven synchroniser for lab-spec documents
    between a parent shared-resource project and any child GCP project.

    Capabilities
    ------------
    • Select / change the active child project
    • List lab-specs in either parent or child
    • Delete lab-specs from the parent (with confirmation)
    • Copy selected labs  parent -> child (down-sync) and child -> parent (up-sync)
      ⤷ includes copying referenced server-image docs in DbCollections.IMAGE
    • Copy selected server-image docs parent -> child and child -> parent
    """

    DEFAULT_REGION = "us-central1"
    DEFAULT_PARENT = "agoge-shared-resources"

    def __init__(
        self,
        parent_project_id: str = DEFAULT_PARENT,
        child_project_id: str | None = None,
    ) -> None:
        self.parent_project_id = parent_project_id
        self.parent_db: DocumentDatabase = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            project_id=self.parent_project_id,
        )

        self.env_mgr = GcloudEnvironmentManager()

        self.child_project_id: str = (
            child_project_id or self._select_child_project()
        )
        self.child_db: DocumentDatabase | None = None
        self._ensure_child_firestore()

    def run(self) -> None:
        """Interactive menu loop."""
        menu: dict[str, tuple[str, Callable[[], None]]] = {
            "1": ("List parent specs", self.list_parent_specs),
            "2": ("List child specs", self.list_child_specs),
            "3": ("Delete spec(s) from parent", self.delete_parent_specs),
            "4": ("Copy lab(s) from parent to child", self.copy_parent_to_child),
            "5": ("Copy lab(s) from child to parent", self.copy_child_to_parent),
            "6": ("Switch child project", self._switch_child_project),
            "7": ("Copy server image(s) from parent to child", self.copy_images_parent_to_child),
            "8": ("Copy server image(s) from child to parent", self.copy_images_child_to_parent),
            "0": ("Return", lambda: None),
        }

        max_key = max(int(k) for k in menu.keys())
        while True:
            print(f"\n{CYAN}=== SharedLabManager ({self.child_project_id}) ==={NC}")
            for k, (label, _) in sorted(menu.items(), key=lambda kv: int(kv[0])):
                print(f"  {k}. {label}")
            choice = input(f"\nSelect an action [0-{max_key}]: ").strip()

            if choice == "0":
                return  # just break out of run()

            action = menu.get(choice)
            if action:
                action[1]()
            else:
                print(f"{RED}Invalid choice.{NC}")

    # ───────────── menu helpers ─────────────
    def list_parent_specs(self) -> None:
        self._list_docs(self.parent_db, "Parent", DbCollections.CATALOG)

    def list_child_specs(self) -> None:
        self._list_docs(self.child_db, f"Child: {self.child_project_id}", DbCollections.CATALOG)

    def delete_parent_specs(self) -> None:
        """Delete one or more specs from the parent after explicit confirmation."""
        specs = self._fetch_docs(self.parent_db, DbCollections.CATALOG)
        if not specs:
            print(f"{YELLOW}No specs found in parent.{NC}")
            return

        to_delete = self._prompt_item_selection(specs, action="delete", item_label="lab-specs")
        if not to_delete:
            print(f"{YELLOW}No specs selected for deletion.{NC}")
            return

        print(f"\n{RED}⚠  Deletion requires confirmation.{NC}")
        for spec in to_delete:
            spec_id = spec["id"]
            prompt = (
                f"Type the spec ID '{spec_id}' to permanently delete it "
                "(or press <Enter> to skip): "
            )
            confirm = input(prompt).strip()
            if confirm != spec_id:
                print(f"  {YELLOW}Skipped '{spec_id}'.{NC}")
                continue

            self.parent_db.delete(
                collection_name=DbCollections.CATALOG,
                doc_id=spec_id,
            )
            print(f"  {RED}Deleted '{spec_id}' from parent.{NC}")

    def copy_parent_to_child(self) -> None:
        """Copy selected labs parent -> child, including referenced server images."""
        specs = self._fetch_docs(self.parent_db, DbCollections.CATALOG)
        if not specs:
            print(f"{YELLOW}Parent contains no specs to copy.{NC}")
            return
        selected = self._prompt_item_selection(specs, action="copy", item_label="lab-specs")
        self._copy_labs_and_images(
            source_db=self.parent_db,
            dest_db=self.child_db,
            selected_specs=selected,
            direction_label="parent ▶ child",
        )

    def copy_child_to_parent(self) -> None:
        """Copy selected labs child -> parent, including referenced server images."""
        specs = self._fetch_docs(self.child_db, DbCollections.CATALOG)
        if not specs:
            print(f"{YELLOW}Child contains no specs to copy.{NC}")
            return
        selected = self._prompt_item_selection(specs, action="copy", item_label="lab-specs")
        self._copy_labs_and_images(
            source_db=self.child_db,
            dest_db=self.parent_db,
            selected_specs=selected,
            direction_label="child ▶ parent",
        )

    # ——— server image copy options ———
    def copy_images_parent_to_child(self) -> None:
        """Copy selected IMAGE docs parent -> child."""
        images = self._fetch_docs(self.parent_db, DbCollections.IMAGE)
        if not images:
            print(f"{YELLOW}Parent contains no server images to copy.{NC}")
            return
        selected = self._prompt_item_selection(images, action="copy", item_label="server images")
        copied = self._copy_docs(self.parent_db, self.child_db, DbCollections.IMAGE, selected)
        print(f"{GREEN}✓  {copied} image(s) copied parent ▶ child.{NC}")

    def copy_images_child_to_parent(self) -> None:
        """Copy selected IMAGE docs child -> parent."""
        images = self._fetch_docs(self.child_db, DbCollections.IMAGE)
        if not images:
            print(f"{YELLOW}Child contains no server images to copy.{NC}")
            return
        selected = self._prompt_item_selection(images, action="copy", item_label="server images")
        copied = self._copy_docs(self.child_db, self.parent_db, DbCollections.IMAGE, selected)
        print(f"{GREEN}✓  {copied} image(s) copied child ▶ parent.{NC}")

    # ───────────── internal helpers ─────────────
    # choose / change child
    def _select_child_project(self) -> str:
        print(f"{CYAN}\nSelect the CHILD project you wish to manage:{NC}")
        self.env_mgr.display_menu()
        env = self.env_mgr.select_environment()
        return self.env_mgr.get_project_id(env)

    def _switch_child_project(self) -> None:
        self.child_project_id = self._select_child_project()
        self.child_db = None
        self._ensure_child_firestore()

    # make sure Firestore exists on child
    def _ensure_child_firestore(self) -> None:
        """Creates the CATALOG Firestore DB on the child if it does not exist."""
        cmd = ShellCommands.FireStore.CHECK_FIRESTORE.value.format(
            project=self.child_project_id,
            database=DATABASE_NAME,
        )
        if subprocess.run(cmd, shell=True, capture_output=True).returncode == 0:
            self.child_db = self._get_child_firestore()
            return  # already exists

        region = (
            input(
                f"Firestore missing on child. Region "
                f"(default {self.DEFAULT_REGION}): "
            )
            or self.DEFAULT_REGION
        )
        create_cmd = ShellCommands.FireStore.CREATE_FIRESTORE.value.format(
            project=self.child_project_id,
            database=DATABASE_NAME,
            region=region,
        )
        print(f"{YELLOW}Creating Firestore on child…{NC}")
        subprocess.run(create_cmd, shell=True, check=True)
        self.child_db = self._get_child_firestore()

    def _get_child_firestore(self) -> DocumentDatabase:
        return DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            project_id=self.child_project_id,
        )

    # generic list / fetch utilities
    @staticmethod
    def _fetch_docs(db: DocumentDatabase, collection: DbCollections) -> List[Dict]:
        return db.query(collection_name=collection)

    @staticmethod
    def _list_docs(db: DocumentDatabase, title: str, collection: DbCollections) -> None:
        docs = db.query(collection_name=collection)
        label = "lab-specs" if collection == DbCollections.CATALOG else "server images"
        if not docs:
            print(f"{YELLOW}{title} has no {label}.{NC}")
            return
        print(f"{CYAN}\n{title} {label}:{NC}")
        for i, d in enumerate(docs, 1):
            print(f"  • {d.get('name') or d.get('id') or f'<unnamed-{i}>'}")
        print(f"{GREEN}Total: {len(docs)}{NC}")

    # selection prompt (reused for specs and images)
    @staticmethod
    def _prompt_item_selection(
        items: List[Dict], *, action: str = "copy", item_label: str = "items"
    ) -> List[Dict]:
        """
        Display items with indexes and return the chosen subset.

        • COPY  : user may type  'a' / 'all'  or a list of indexes.
        • DELETE: user must type one or more indexes; blank = no deletion.
        """
        print(f"\nAvailable {item_label}:")
        for idx, item in enumerate(items, 1):
            label = item.get("name") or item.get("id") or f"<unnamed-{idx}>"
            print(f"  [{idx:>2}] {label}")

        if action == "copy":
            raw = input(
                f"\nEnter number(s) to COPY {item_label} (comma/space-separated) "
                "or 'a' for all: "
            ).strip().lower()
            if raw in {"a", "all"}:
                return items  # everything
        else:  # delete
            raw = input(
                f"\nEnter number(s) to DELETE {item_label} (comma/space-separated). "
                "Press <Enter> to cancel: "
            ).strip().lower()
            if not raw:
                return []  # nothing chosen

        chosen: List[Dict] = []
        idx_tokens = {tok for tok in raw.replace(",", " ").split() if tok}
        for tok in idx_tokens:
            if not tok.isdigit():
                print(f"⚠️  Ignoring non-numeric token '{tok}'.")
                continue
            i = int(tok)
            if 1 <= i <= len(items):
                chosen.append(items[i - 1])
            else:
                print(f"⚠️  Index {i} is out of range; skipped.")

        return chosen

    # ——— lab + referenced image copy helpers ———
    def _copy_labs_and_images(
        self,
        source_db: DocumentDatabase,
        dest_db: DocumentDatabase,
        selected_specs: List[Dict],
        direction_label: str,
    ) -> None:
        if not selected_specs:
            print(f"{YELLOW}No labs selected.{NC}")
            return

        # 1) Copy labs
        for spec in selected_specs:
            dest_db.update(
                collection_name=DbCollections.CATALOG,
                doc_id=spec["id"],
                data=spec,
            )
            print(f"  {GREEN}Copied lab '{spec['id']}' ▶ {direction_label}.{NC}")

        # 2) Collect referenced server-image IDs
        image_ids = self._collect_image_ids_from_specs(selected_specs)
        if not image_ids:
            print(f"{YELLOW}No referenced server images found in selected labs.{NC}")
            print(f"{GREEN}✓  {len(selected_specs)} spec(s) copied to {direction_label}.{NC}")
            return

        # 3) Copy those IMAGE docs
        copied, missing = self._copy_images_by_ids(source_db, dest_db, image_ids)

        print(f"{GREEN}✓  {len(selected_specs)} spec(s) copied to {direction_label}.{NC}")
        print(f"{GREEN}✓  {copied} referenced image(s) copied to {direction_label}.{NC}")
        if missing:
            print(f"{YELLOW}⚠  {len(missing)} image(s) referenced by labs were not found in source: {', '.join(sorted(missing))}{NC}")

    @staticmethod
    def _collect_image_ids_from_specs(specs: List[Dict]) -> Set[str]:
        """
        Collect string-valued `image` IDs from the *top-level* `servers` list
        in each selected lab spec.

        Expected shape per spec:
          {
            "id": "...",
            "servers": [
                {"name": "...", "image": "image-doc-id", ...},
                ...
            ],
            ...
          }
        """
        image_ids: Set[str] = set()
        for spec in specs:
            servers = spec.get("servers")
            if not isinstance(servers, list):
                continue
            for srv in servers:
                if isinstance(srv, dict):
                    img = srv.get("image")
                    if isinstance(img, str) and img.strip():
                        image_ids.add(img.strip())
        return image_ids

    def _copy_images_by_ids(
            self,
            source_db: DocumentDatabase,
            dest_db: DocumentDatabase,
            image_ids: set[str],
    ) -> tuple[int, set[str]]:
        """
        Copy a set of IMAGE docs by *document ID* (i.e., the 'name' field in IMAGE).
        Returns (copied_count, missing_ids).
        """
        # Build an index of all source IMAGE docs keyed by their actual doc ID
        src_images = {}
        for img in source_db.query(collection_name=DbCollections.IMAGE):
            key = self._doc_id_for(DbCollections.IMAGE, img)
            if key:
                src_images[key] = img

        missing: set[str] = set()
        copied = 0
        for img_id in image_ids:
            data = src_images.get(img_id)
            if not data:
                missing.add(img_id)
                continue
            dest_db.update(
                collection_name=DbCollections.IMAGE,
                doc_id=img_id,  # IMAGE doc ID is the 'name' value
                data=data,
            )
            copied += 1
        return copied, missing

    def _copy_docs(
            self,
            source_db: DocumentDatabase,
            dest_db: DocumentDatabase,
            collection: DbCollections,
            items: List[Dict],
    ) -> int:
        """Generic copy helper for arbitrary docs (e.g., IMAGE, CATALOG)."""
        copied = 0
        for item in items:
            doc_id = self._doc_id_for(collection, item)
            if not doc_id:
                print(f"{YELLOW}Skipping item with no resolvable doc ID (id/name missing).{NC}")
                continue
            dest_db.update(
                collection_name=collection,
                doc_id=doc_id,
                data=item,
            )
            copied += 1
            print(f"  {GREEN}Copied '{doc_id}'.{NC}")
        return copied

    def _doc_id_for(self, collection: DbCollections, doc: Dict) -> str | None:
        """
        Returns the Firestore doc ID for a doc in the given collection.
        - CATALOG uses 'id'
        - IMAGE   uses 'name'
        Falls back to either field if the preferred one is missing.
        """
        if collection == DbCollections.IMAGE:
            return doc.get("name") or doc.get("id")
        return doc.get("id") or doc.get("name")
