from colorama import Fore, Style

from cloud_deployment.utilities.menu_options import ProjectMaintenanceOptions


project_maintenance_menu = {
    "label": "Project Maintenance",
    "options": [
        (ProjectMaintenanceOptions.REIMAGE_GUACAMOLE, ProjectMaintenanceOptions.REIMAGE_GUACAMOLE.description),
        (ProjectMaintenanceOptions.BACK, ProjectMaintenanceOptions.BACK.description),
    ],
}


def display_project_maintenance_menu() -> None:
    print(Fore.BLUE + f"\n-- {project_maintenance_menu['label']} --" + Style.RESET_ALL)
    for idx, (_, description) in enumerate(project_maintenance_menu["options"], start=1):
        print(f"{idx}. {description}")
    print("")


def get_project_maintenance_selection(choice: int) -> ProjectMaintenanceOptions:
    return project_maintenance_menu["options"][choice - 1][0]