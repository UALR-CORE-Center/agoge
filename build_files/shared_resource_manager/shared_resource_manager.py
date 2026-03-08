from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from enum import Enum
from typing import Callable, Dict

from colorama import Fore, Style, init

from cloud_deployment.operations.images_and_specs.default_server_image import (
    DefaultServerImage,
)
from cloud_deployment.operations.env_and_quotas.environment_variables import (
    EnvironmentVariables,
)
from cloud_deployment.operations.env_and_quotas.gcloud_environment_manager import (
    GcloudEnvironmentManager,
)

init(autoreset=True)

class CentralOps(Enum):
    ALL = 0
    SYNC_LABS = 1
    SYNC_IMAGES = 2
    SYNC_ENV = 3
    EXIT = 99

    @property
    def label(self) -> str:
        return {
            self.ALL: "Run ALL maintenance tasks",
            self.SYNC_LABS: "Synchronize upstream labs (Firestore)",
            self.SYNC_IMAGES: "Refresh/copy default server images",
            self.SYNC_ENV: "Synchronize environment variables",
            self.EXIT: "Exit",
        }[self]


# Lambdas here let you add new operations with one line
operation_map: Dict[CentralOps, Callable[[str], None]] = {
    CentralOps.SYNC_IMAGES: lambda pid: DefaultServerImage(project=pid).run(),
    CentralOps.SYNC_ENV: lambda pid: EnvironmentVariables(project=pid).run(),
}

def set_account_and_project() -> str:
    """
    • Uses the shared-resource configuration only.
    • Requires an authenticated gcloud account.
    • Always offers the user a chance to switch accounts.
    • Switches to the single shared-resource environment and returns its
      project-id.
    """
    env_mgr = GcloudEnvironmentManager()

    # ----- Account ------------------------------------------------------
    current = env_mgr.get_current_account()
    if not current:
        print(
            Fore.RED
            + "[!!] No gcloud account authenticated. Run `gcloud auth login`."
            + Style.RESET_ALL
        )
        raise SystemExit(1)

    print(Fore.CYAN + f"Using account: {current}" + Style.RESET_ALL)
    env_mgr.set_account()        # always offer an interactive switch

    sel_env   = env_mgr.select_environment()
    project_id = env_mgr.switch_environment(sel_env)

    print(Fore.GREEN + f"Active GCP project → {project_id}" + Style.RESET_ALL)
    return project_id


# ── Main driver ───────────────────────────────────────────────────────────
def main() -> None:
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--task",
        "-t",
        type=int,
        choices=[op.value for op in CentralOps],
        help="Run a single task (numeric enum value) and exit (good for cron)",
    )
    args = parser.parse_args()

    # Will raise if auth missing
    project_id = set_account_and_project()

    # Determine interactive vs single-shot
    pending = [CentralOps(args.task)] if args.task is not None else None

    while True:
        if pending is None:  # Interactive menu
            print(Fore.YELLOW + "\n=== Central Maintenance Menu ===" + Style.RESET_ALL)
            for op in CentralOps:
                print(f"{op.value}. {op.label}")
            try:
                choice = CentralOps(int(input("Select task: ").strip()))
            except (ValueError, KeyError):
                print(Fore.RED + "Invalid choice; try again." + Style.RESET_ALL)
                continue
            pending = [choice]

        # Execute chosen tasks
        for op in pending:
            if op == CentralOps.EXIT:
                print(Fore.YELLOW + "Goodbye!" + Style.RESET_ALL)
                return

            if op == CentralOps.ALL:
                for sub in (CentralOps.SYNC_LABS, CentralOps.SYNC_IMAGES, CentralOps.SYNC_ENV):
                    operation_map[sub](project_id)
            else:
                operation_map[op](project_id)

        if args.task is not None:  # single-shot finished
            break
        pending = None  # loop back in interactive mode


if __name__ == "__main__":
    main()
