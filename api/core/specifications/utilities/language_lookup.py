import re

from common.exceptions import AgogeValidationError


class LanguageLookup:
    # Dictionary mapping file extensions to programming languages
    extension_map = {
        '.py': 'Python',
        '.pyw': 'Python',
        '.js': 'Javascript',
        '.mjs': 'Javascript',
        '.cjs': 'Javascript',
        '.ps1': 'Powershell',
        '.psm1': 'Powershell',
        '.psd1': 'Powershell',
        '.sh': 'Bash',
        '.bash': 'Bash',
        '.bsh': 'Bash',
        '.go': 'Go',
    }

    @classmethod
    def get_language(cls, filename: str) -> str:
        """
        Returns the programming language based on the file extension.

        Args:
            filename (str): The filename to check.

        Returns:
            str: The programming language corresponding to the file extension.
        """
        # Extract the file extension
        extension = filename.rsplit('.', 1)[-1]
        extension = f'.{extension}'

        # Return the language or raise an error if not found
        if extension in cls.extension_map:
            return cls.extension_map[extension]
        else:
            raise ValueError(f"Unknown file extension: {extension}")

    @classmethod
    def validate(cls, filename: str) -> str:
        file_name = filename.rsplit('.', 1)[0]

        pattern = r'^[a-zA-Z0-9\-]{1,63}$'
        valid_name = re.match(pattern, file_name)

        if not valid_name:
            raise AgogeValidationError("Invalid filename")

        return cls.get_language(filename)
