# agoge/setup.py
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from colorama import Fore, Style, init

from cloud_deployment.operations.env_and_quotas.gcloud_environment_manager import GcloudEnvironmentManager
from cloud_deployment.utilities.menu_options import (
    SetupCategories,
    display_main_menu,
    display_sub_menu,
    get_user_selection,
    category_menu
)
from cloud_deployment.setup_manager import SetupManager
from cloud_deployment.operations.lab_management.shared_lab_manager import SharedLabManager
from common.constants.build_constants import BuildConstants
from common.exceptions import AgogeValidationError
from cloud_deployment.operations.env_and_quotas.project_menu import ProjectMenu

init(autoreset=True)


def main():
    """
    Entry point for the setup script.
    Handles:
      1. Parsing command-line arguments.
      2. Managing gcloud account and environment selection.
      3. Displaying and processing menu options for various setup tasks.
    """
    # Parse arguments
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "-s",
        "--suppress",
        default=None,
        help="Suppress input prompts and accept all defaults."
    )
    parser.add_argument(
        "-u",
        "--use-shared-resource",
        default=True,
        help="Whether to use the central shared resources for the project"
    )
    parser.add_argument(
        "--reauthenticate",
        "--refresh-gcp-auth",
        action="store_true",
        help=(
            "Force a browser login and refresh both gcloud credentials and "
            "Application Default Credentials before setup starts."
        ),
    )
    parser.add_argument(
        '--hide-environment', action='append', default=[], metavar='PROJECT_OR_NAME',
        help='Hide an entry in the shared setup menu without deleting its GCP project.',
    )
    parser.add_argument(
        '--show-environment', action='append', default=[], metavar='PROJECT_OR_NAME',
        help='Restore a hidden setup menu entry.',
    )
    parser.add_argument(
        '--rename-environment', action='append', nargs=2, default=[],
        metavar=('PROJECT_OR_NAME', 'MENU_NAME'),
        help='Change a shared setup menu label without changing the project ID or URL path.',
    )
    args = vars(parser.parse_args())
    suppress = args['suppress']  # Not currently used, but set up for future expansions
    use_shared_resource = args['use_shared_resource']

    # Authenticate before the environment manager queries the shared Firestore
    # database. gcloud and Python client libraries use separate credential
    # stores, so both must be checked and synchronized first.
    env_manager = GcloudEnvironmentManager(load_configurations=False)
    current_account = env_manager.get_current_account()

    if current_account:
        print(Fore.CYAN + f"Currently logged in as: {current_account}" + Style.RESET_ALL)
    else:
        print(
            Fore.YELLOW
            + "[!] No active Google Cloud account found. Setup can authenticate now."
            + Style.RESET_ALL
        )

    # Allow user to pick/change accounts and environments
    selected_account = env_manager.set_account()
    env_manager.ensure_credentials(
        account=selected_account,
        quota_project=BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT,
        force=args["reauthenticate"],
        # A valid ADC token can still belong to a different account than the
        # selected gcloud identity. A non-forced login reuses cached credentials
        # while ensuring both stores use the selected account.
        synchronize=bool(selected_account),
    )
    if args['hide_environment'] or args['show_environment'] or args['rename_environment']:
        ProjectMenu().update(
            hide=args['hide_environment'], show=args['show_environment'],
            rename=args['rename_environment'],
        )
        env_manager.load_configurations()
        env_manager.display_menu()
        return
    env_manager.load_configurations()
    env_manager.display_menu()
    selected_env = env_manager.select_environment()
    project_id = env_manager.switch_environment(selected_env)

    # Main interactive loop
    while True:
        # 1. Display the main category menu (top-level)
        display_main_menu()
        category_choice = get_user_selection(len(SetupCategories))
        selected_category = SetupCategories(category_choice)

        if selected_category == SetupCategories.EXIT:
            print(Fore.YELLOW + "Exiting the setup script. Goodbye!" + Style.RESET_ALL)
            break
        elif selected_category == SetupCategories.SHARED_LAB_MANAGEMENT:
            SharedLabManager().run()    # This has a separate menu system. Process this and continue the next selection.
            continue


        # 2. Display the sub-menu for the chosen category
        display_sub_menu(selected_category)
        sub_options = category_menu[selected_category]["options"]

        # 3. Process the user’s sub-menu choice
        sub_choice = get_user_selection(len(sub_options))
        chosen_option, _ = sub_options[sub_choice - 1]  # (SetupOptions, description)

        if chosen_option == SetupCategories.BACK:
            continue

        # 4. Run the selected setup operation
        setup_manager = SetupManager(selection=chosen_option, project=project_id)
        setup_manager.run()


if __name__ == '__main__':
    try:
        main()
    except AgogeValidationError as exc:
        print(Fore.RED + f"[!!] {exc}" + Style.RESET_ALL)
        raise SystemExit(1) from exc
