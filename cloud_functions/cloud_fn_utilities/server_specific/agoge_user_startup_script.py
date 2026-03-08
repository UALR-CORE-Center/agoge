from typing import List


class AgogeUserStartupScript:
    def __init__(
        self,
        username: str,
        password: str,
        ssh_key: str = None,
    ) -> None:
        self.username = username
        self.ssh_key = ssh_key
        self.password = password

    @staticmethod
    def unix_prefix() -> str:
        return "#!/bin/bash"

    def get_unix_script(self) -> List[str]:
        script_lines = [
            f"USERNAME=\"{self.username}\"",
            f"PASSWORD=\"{self.password}\"",
            f"SSH_KEY=\"{self.ssh_key}\"",
            "sudo useradd -m -s /bin/bash \"$USERNAME\"",
            "echo \"$USERNAME:$PASSWORD\" | sudo chpasswd",
            "sudo usermod -aG sudo \"$USERNAME\"",
            "sudo mkdir -p /home/$USERNAME/.ssh",
            "echo \"$SSH_KEY\" | sudo tee /home/$USERNAME/.ssh/authorized_keys",
            "sudo chown -R $USERNAME:$USERNAME /home/$USERNAME/.ssh",
            "sudo chmod 700 /home/$USERNAME/.ssh",
            "sudo chmod 600 /home/$USERNAME/.ssh/authorized_keys"
        ]
        return script_lines

    def get_windows_script(self) -> List[str]:
        script_lines = [
            '# Creates the Agoge user if it does not exist.\n',
            f'$user = "{self.username}"',
            f'$password = ConvertTo-SecureString "{self.password}" -AsPlainText -Force\n',
            '$UserExists = Get-LocalUser | Where-Object {$_.Name -eq $user} | Select-Object -ExpandProperty Name\n',
            'if (-not $UserExists) {',
            '    New-LocalUser -Name $user -Password $password -PasswordNeverExpires -UserMayNotChangePassword',
            '    Add-LocalGroupMember -Group "Administrators" -Member $user',
            '}'
        ]

        if self.ssh_key:
            script_lines += [
                '# Install OpenSSH Server if not installed',
                'if (-not (Get-WindowsCapability -Online | Where-Object Name -like "OpenSSH.Server*").State -eq "Installed") {',
                '    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0',
                '    Start-Service sshd',
                '    Set-Service -Name sshd -StartupType \'Automatic\'',
                '    New-NetFirewallRule -Name sshd -DisplayName \'OpenSSH Server (sshd)\' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22',
                '}\n',
                '# Setup SSH directory and authorized_keys for the user',
                f'$sshDir = "C:\\Users\\$user\\.ssh"',
                'if (-not (Test-Path $sshDir)) {',
                '    New-Item -Path $sshDir -ItemType Directory -Force',
                '    Set-ItemProperty -Path $sshDir -Name IsReadOnly -Value $false',
                '}\n',
                '# Add SSH public key to authorized_keys',
                f'$sshKey = "{self.ssh_key}"',
                f'$authorizedKeys = "$sshDir\\authorized_keys"',
                'if (-not (Test-Path $authorizedKeys)) {',
                '    Set-Content -Path $authorizedKeys -Value $sshKey',
                '} else {',
                '    Add-Content -Path $authorizedKeys -Value $sshKey',
                '}\n',
                '# Set permissions for the .ssh folder and authorized_keys',
                'icacls $sshDir /inheritance:r /grant "${user}:(F)"',
                'icacls $authorizedKeys /inheritance:r /grant "${user}:(F)"',
                'icacls $sshDir /inheritance:r /grant "SYSTEM:(F)"'
            ]

        return script_lines


class MetadataKey:
    """
    Metadata keys used for specifying startup scripts.
    Windows keys are defined here -
        `https://cloud.google.com/compute/docs/instances/startup-scripts/windows#order_of_execution_of_windows_startup_scripts`
    """
    LINUX = 'startup-script'
    WINDOWS = 'sysprep-specialize-script-ps1'
