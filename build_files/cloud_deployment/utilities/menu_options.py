from enum import Enum
from colorama import Fore, Style, init

init(autoreset=True)


class SetupCategories(Enum):
    """
    Top-level menu categories for setup operations.
    """
    APP_INSTALL_UPDATES = 1
    IMAGES_AND_SPECS = 2
    ENV_AND_QUOTAS = 3
    PROJECTS = 4
    SHARED_LAB_MANAGEMENT = 5
    BACK = 6
    EXIT = 99


class SetupOptions(bytes, Enum):
    """
    Enum for all available setup options, each with a numeric value and description.
    """
    def __new__(cls, value, description):
        obj = bytes.__new__(cls, [value])
        obj._value_ = value
        obj.description = description
        return obj

    # Update actions
    FULL = (0, "Full Agoge Installation")
    UPDATE = (1, "Update Main Application and Cloud Functions")
    CLOUD_FUNCTION = (2, "Update Cloud Function Only")
    MAIN_APP = (3, "Update Main Application Only")
    CLASSIFIED_APP = (5, "Update Classified Application Only")

    # Images
    DEFAULT_SERVER_IMAGES = (4, "Copy Over Default Server Images")
    IMPORT_CUSTOM_IMAGES = (6, "Import Custom Images from GCP into App")
    IMPORT_LOCAL_IMAGE = (7, "Import Custom Image from Local Environment into App")
    STARTUP_SCRIPTS_AND_INSTRUCTIONS = (11, "Synchronize Startup Scripts and Instructions")
    REFRESH_GUACAMOLE_IMAGE_AND_CERT = (12, "Refresh/Create guacamole image and certificate.")

    # Environment & Quotas
    ENV = (10, "Synchronize Environment Variables")
    INCREASE_QUOTAS = (13, "Increase Quotas (EXPERIMENTAL)")

    # Projects
    PROJECT_CREATION = (14, "Create a New GCP Production Project")
    PROJECT_EDIT = (15, "Edit Settings for an Existing GCP Production Project")
    PROJECT_DELETE = (16, "Delete a GCP Production Project")

    # Shared Labs
    SHARED_LAB_MANAGEMENT = (20, "Managed Shared Labs")

    # Back
    BACK = (30, "Back to Main Menu")

    # Exit
    EXIT = (40, "Exit")

# Organize categories and their sub-options
category_menu = {
    SetupCategories.APP_INSTALL_UPDATES: {
        "label": "Application Installation and Updates",
        "options": [
            (SetupOptions.FULL, SetupOptions.FULL.description),
            (SetupOptions.UPDATE, SetupOptions.UPDATE.description),
            (SetupOptions.CLOUD_FUNCTION, SetupOptions.CLOUD_FUNCTION.description),
            (SetupOptions.MAIN_APP, SetupOptions.MAIN_APP.description),
            (SetupOptions.CLASSIFIED_APP, SetupOptions.CLASSIFIED_APP.description),
            (SetupOptions.BACK, SetupOptions.BACK.description),
        ],
    },
    SetupCategories.IMAGES_AND_SPECS: {
        "label": "Server Images & Build Specs",
        "options": [
            (SetupOptions.DEFAULT_SERVER_IMAGES, SetupOptions.DEFAULT_SERVER_IMAGES.description),
            (SetupOptions.IMPORT_CUSTOM_IMAGES, SetupOptions.IMPORT_CUSTOM_IMAGES.description),
            (SetupOptions.IMPORT_LOCAL_IMAGE, SetupOptions.IMPORT_LOCAL_IMAGE.description),
            (SetupOptions.STARTUP_SCRIPTS_AND_INSTRUCTIONS,
             SetupOptions.STARTUP_SCRIPTS_AND_INSTRUCTIONS.description),
            (SetupOptions.REFRESH_GUACAMOLE_IMAGE_AND_CERT, SetupOptions.REFRESH_GUACAMOLE_IMAGE_AND_CERT.description),
            (SetupOptions.BACK, SetupOptions.BACK.description),
        ],
    },
    SetupCategories.ENV_AND_QUOTAS: {
        "label": "Environment & Quotas",
        "options": [
            (SetupOptions.ENV, SetupOptions.ENV.description),
            (SetupOptions.INCREASE_QUOTAS, SetupOptions.INCREASE_QUOTAS.description),
            (SetupOptions.BACK, SetupOptions.BACK.description),
        ],
    },
    SetupCategories.PROJECTS: {
        "label": "GCP Project Creation/Management",
        "options": [
            (SetupOptions.PROJECT_CREATION, SetupOptions.PROJECT_CREATION.description),
            (SetupOptions.PROJECT_EDIT, SetupOptions.PROJECT_EDIT.description),
            (SetupOptions.PROJECT_DELETE, SetupOptions.PROJECT_DELETE.description),
            (SetupOptions.BACK, SetupOptions.BACK.description),
        ],
    },
    SetupCategories.SHARED_LAB_MANAGEMENT: {
        "label": "Shared Lab Management",
        "options": [
            (SetupOptions.SHARED_LAB_MANAGEMENT, SetupOptions.SHARED_LAB_MANAGEMENT.description),
        ],
    },
    SetupCategories.BACK: {
        "label": "Back",
        "options": [
            (SetupOptions.BACK, SetupOptions.BACK.description),
        ],
    },
    SetupCategories.EXIT: {
        "label": "Exit",
        "options": [
            (SetupOptions.EXIT, SetupOptions.EXIT.description),
        ],
    }
}


def display_main_menu():
    """
    Displays the main category menu (top-level), allowing the user to choose
    among predefined SetupCategories.
    """
    print(Fore.YELLOW + "=== Select a Category ===" + Style.RESET_ALL)
    for category in SetupCategories:
        category_label = category_menu[category]["label"]
        if category_label == 'Back':
            continue
        print(Fore.GREEN + f"{category.value}. {category_label}")
    print(Style.RESET_ALL, end="")


def display_sub_menu(selected_category: SetupCategories):
    """
    Displays the sub-menu options for a given category, such as 'Full or Partial Updates'.
    """
    sub_options = category_menu[selected_category]["options"]
    print(Fore.BLUE + f"\n-- {category_menu[selected_category]['label']} --" + Style.RESET_ALL)
    for idx, (enum_option, description) in enumerate(sub_options, start=1):
        print(f"{idx}. {description}")
    print("")


def get_user_selection(max_choice: int) -> int:
    """
    Prompts the user for numeric input, ensuring the chosen value is within
    the valid range [1..max_choice].
    """
    while True:
        try:
            choice = int(input("Enter your choice: ").strip())
            if 1 <= choice <= max_choice:
                return choice
            else:
                print(Fore.RED + f"Invalid choice. Please enter a number between 1 and {max_choice}."
                      + Style.RESET_ALL)
        except ValueError:
            print(Fore.RED + "Invalid input. Please enter a valid number." + Style.RESET_ALL)
