from colorama import Fore, init
from datetime import datetime

init(autoreset=True)


class Message:
    """
    Formatted output messages for better CLI experiences.
    """
    @staticmethod
    def _current_time() -> str:
        now = datetime.now()
        return f"{Fore.WHITE}[{now.hour}:{now.minute}]{Fore.RESET}"

    def confirm(
        self,
        message: str,
        confirm_value: str = None
    ) -> bool:
        if confirm_value:
            formatted = f"{Fore.RESET}{message} [{Fore.CYAN}{confirm_value}{Fore.RESET}]?"
        else:
            formatted = f"{Fore.RESET}{message}?"

        while True:
            choice = input(f"{formatted} (y/n): ").strip().lower()
            if choice in ["y", "n"]:
                return choice == "y"
            else:
                self.error("Invalid choice. Please enter 'y' or 'n'.")

    def info(self, message: str) -> None:
        now = self._current_time()
        print(f"{Fore.BLUE}[INFO]{now}{Fore.LIGHTWHITE_EX} {message}")

    def success(self, message) -> None:
        now = self._current_time()
        print(f"{Fore.GREEN}[SUCCESS]{now}{Fore.LIGHTWHITE_EX} {message}")

    def error(self, message) -> None:
        now = self._current_time()
        print(f"{Fore.RED}[ERROR]{now}{Fore.WHITE} {message}")

    def default(self, message: str, indent: bool = False) -> None:
        if indent:
            print(f"  {Fore.WHITE}{message}{Fore.RESET}")
        else:
            print(f"{Fore.WHITE}{message}{Fore.RESET}")

    def warning(self, message: str) -> None:
        now = self._current_time()
        print(f"{Fore.YELLOW}[WARNING]{now}{Fore.LIGHTWHITE_EX} {message}")
