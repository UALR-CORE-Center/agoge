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
    args = vars(parser.parse_args())
    suppress = args['suppress']  # Not currently used, but set up for future expansions
    use_shared_resource = args['use_shared_resource']

    # Instantiate environment manager
    env_manager = GcloudEnvironmentManager()
    current_account = env_manager.get_current_account()

    if current_account:
        print(Fore.CYAN + f"Currently logged in as: {current_account}" + Style.RESET_ALL)
    else:
        print(Fore.RED + "[!!] No active Google Cloud account found. Please log in before continuing."
              + Style.RESET_ALL)
        # Optionally exit here, or allow user interaction to continue for login
        # e.g., return or exit(1)
        return

    # Allow user to pick/change accounts and environments
    env_manager.set_account()
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
    main()
