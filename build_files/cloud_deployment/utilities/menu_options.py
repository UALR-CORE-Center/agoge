# agoge/cloud_deployment/utilities/menu_options.py
from enum import Enum

from cloud_deployment.utilities import console as ui


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
    SHARED_LOAD_BALANCER = (22, "Configure Shared Load Balancer Routing")

    # Images
    DEFAULT_SERVER_IMAGES = (4, "Copy Over Default Server Images")
    IMPORT_CUSTOM_IMAGES = (6, "Import Custom Images from GCP into App")
    IMPORT_LOCAL_IMAGE = (7, "Import Custom Image from Local Environment into App")
    STARTUP_SCRIPTS_AND_INSTRUCTIONS = (11, "Synchronize Startup Scripts and Instructions")
    REFRESH_GUACAMOLE_IMAGE_AND_CERT = (12, "Refresh/Create guacamole image and certificate.")
    SYNC_PUBLIC_IMAGES = (23, "Synchronize Public OS Images")
    NESTED_MEDIA_BUCKET = (24, "Configure Nested Image Media Bucket")
    NESTED_OS_CATALOG = (25, "Synchronize Nested Guest OS Catalog")

    # Environment & Quotas
    ENV = (10, "Synchronize Environment Variables")
    INCREASE_QUOTAS = (13, "Increase Quotas (EXPERIMENTAL)")
    REFRESH_GCP_CREDENTIALS = (21, "Refresh gcloud and Python GCP Credentials")

    # Projects
    PROJECT_CREATION = (14, "Create a New GCP Project")
    PROJECT_EDIT = (15, "Edit Settings for an Existing GCP Production Project")
    PROJECT_DELETE = (16, "Delete a GCP Production Project")
    PROJECT_MAINTENANCE = (17, "Perform Maintenance Operations on a GCP Production Project")

    # Shared Labs
    SHARED_LAB_MANAGEMENT = (20, "Managed Shared Labs")

    # Back
    BACK = (30, "Back to Main Menu")

    # Exit
    EXIT = (40, "Exit")


class ProjectMaintenanceOptions(bytes, Enum):
    """
    Enum for project maintenance submenu options.
    """
    def __new__(cls, value, description):
        obj = bytes.__new__(cls, [value])
        obj._value_ = value
        obj.description = description
        return obj

    REIMAGE_GUACAMOLE = (1, "Reimage Guacamole Server (Refresh TLS Certificate)")
    EXTEND_PROJECT_EXPIRATION = (2, "Extend Project Expiration Date")
    REBUILD_WORKOUTS = (3, "Rebuild All or Selected Workouts in a Unit")
    BACK = (99, "Back")


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
            (SetupOptions.SHARED_LOAD_BALANCER, SetupOptions.SHARED_LOAD_BALANCER.description),
            (SetupOptions.BACK, SetupOptions.BACK.description),
        ],
    },
    SetupCategories.IMAGES_AND_SPECS: {
        "label": "Server Images & Build Specs",
        "options": [
            (SetupOptions.DEFAULT_SERVER_IMAGES, SetupOptions.DEFAULT_SERVER_IMAGES.description),
            (SetupOptions.IMPORT_CUSTOM_IMAGES, SetupOptions.IMPORT_CUSTOM_IMAGES.description),
            (SetupOptions.IMPORT_LOCAL_IMAGE, SetupOptions.IMPORT_LOCAL_IMAGE.description),
            (
                SetupOptions.STARTUP_SCRIPTS_AND_INSTRUCTIONS,
                SetupOptions.STARTUP_SCRIPTS_AND_INSTRUCTIONS.description,
            ),
            (
                SetupOptions.REFRESH_GUACAMOLE_IMAGE_AND_CERT,
                SetupOptions.REFRESH_GUACAMOLE_IMAGE_AND_CERT.description,
            ),
            (SetupOptions.SYNC_PUBLIC_IMAGES, SetupOptions.SYNC_PUBLIC_IMAGES.description),
            (SetupOptions.NESTED_MEDIA_BUCKET, SetupOptions.NESTED_MEDIA_BUCKET.description),
            (SetupOptions.NESTED_OS_CATALOG, SetupOptions.NESTED_OS_CATALOG.description),
            (SetupOptions.BACK, SetupOptions.BACK.description),
        ],
    },
    SetupCategories.ENV_AND_QUOTAS: {
        "label": "Environment & Quotas",
        "options": [
            (
                SetupOptions.REFRESH_GCP_CREDENTIALS,
                SetupOptions.REFRESH_GCP_CREDENTIALS.description,
            ),
            (SetupOptions.ENV, SetupOptions.ENV.description),
            (SetupOptions.INCREASE_QUOTAS, SetupOptions.INCREASE_QUOTAS.description),
            (SetupOptions.BACK, SetupOptions.BACK.description),
        ],
    },
    SetupCategories.PROJECTS: {
        "label": "GCP Project Management & Maintenance",
        "options": [
            (SetupOptions.PROJECT_CREATION, SetupOptions.PROJECT_CREATION.description),
            (SetupOptions.PROJECT_EDIT, SetupOptions.PROJECT_EDIT.description),
            (SetupOptions.PROJECT_DELETE, SetupOptions.PROJECT_DELETE.description),
            (SetupOptions.PROJECT_MAINTENANCE, SetupOptions.PROJECT_MAINTENANCE.description),
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


def get_main_menu_categories() -> list[SetupCategories]:
    """
    Returns the categories shown in the main menu, in display order.
    """
    return [category for category in SetupCategories if category_menu[category]["label"] != "Back"]


def display_main_menu():
    """
    Displays the main category menu (top-level), allowing the user to choose
    among predefined SetupCategories.
    """
    ui.menu("Main menu", (
        (category.value, category_menu[category]["label"]) for category in get_main_menu_categories()
    ))


def display_sub_menu(selected_category: SetupCategories):
    """
    Displays the sub-menu options for a given category.
    """
    sub_options = category_menu[selected_category]["options"]
    ui.menu(
        category_menu[selected_category]["label"],
        ((idx, description) for idx, (_, description) in enumerate(sub_options, start=1)),
    )


def get_setup_selection(selected_category: SetupCategories, choice: int) -> SetupOptions:
    """
    Returns the SetupOptions enum corresponding to the selected submenu choice.
    """
    return category_menu[selected_category]["options"][choice - 1][0]


def get_user_selection(max_choice: int = None, valid_choices: list[int] = None) -> int:
    """
    Prompts the user for numeric input. The value must be in valid_choices when
    given, otherwise within the range [1..max_choice]. A trailing period is
    ignored so that "99." is accepted like the menu displays it.
    """
    if valid_choices is None:
        valid_choices = list(range(1, max_choice + 1))
    while True:
        try:
            choice = int(ui.prompt("Enter your choice:").strip().rstrip("."))
            if choice in valid_choices:
                return choice
            ui.error(f"Invalid choice. Please enter one of: {', '.join(str(c) for c in valid_choices)}.")
        except ValueError:
            ui.error("Invalid input. Please enter a valid number.")


# ------------------------------
# Single-source registry section
# ------------------------------

from cloud_deployment.operations.project_maintenance.rebuild_guacamole_for_unit import RebuildGuacamoleForUnit
from cloud_deployment.operations.project_maintenance.extend_project_expiration import ExtendWorkoutExpirations
from cloud_deployment.operations.project_maintenance.rebuild_workouts import RebuildWorkouts


PROJECT_MAINTENANCE_REGISTRY = [
    {
        "option": ProjectMaintenanceOptions.REIMAGE_GUACAMOLE,
        "description": ProjectMaintenanceOptions.REIMAGE_GUACAMOLE.description,
        "operation_class": RebuildGuacamoleForUnit,
    },
    {
        "option": ProjectMaintenanceOptions.EXTEND_PROJECT_EXPIRATION,
        "description": ProjectMaintenanceOptions.EXTEND_PROJECT_EXPIRATION.description,
        "operation_class": ExtendWorkoutExpirations,
    },
    {
        "option": ProjectMaintenanceOptions.REBUILD_WORKOUTS,
        "description": ProjectMaintenanceOptions.REBUILD_WORKOUTS.description,
        "operation_class": RebuildWorkouts,
    },
    {
        "option": ProjectMaintenanceOptions.BACK,
        "description": ProjectMaintenanceOptions.BACK.description,
        "operation_class": None,
    },
]


def display_project_maintenance_menu():
    ui.menu("Project maintenance", (
        (idx, item["description"]) for idx, item in enumerate(PROJECT_MAINTENANCE_REGISTRY, start=1)
    ))


def get_project_maintenance_selection(choice: int) -> ProjectMaintenanceOptions:
    return PROJECT_MAINTENANCE_REGISTRY[choice - 1]["option"]


def get_project_maintenance_operation(choice: int):
    return PROJECT_MAINTENANCE_REGISTRY[choice - 1]["operation_class"]


def get_project_maintenance_menu_length() -> int:
    return len(PROJECT_MAINTENANCE_REGISTRY)
