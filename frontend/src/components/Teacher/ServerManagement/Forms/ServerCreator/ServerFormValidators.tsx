export const validateServerName = (name: string) => {
    const regex = /^[a-z]([-a-z0-9]*[a-z0-9])?$/;
    if (!regex.test(name)) {
        return "Name must start with a lowercase letter, followed by up to 55 lowercase letters, " +
            "numbers, or hyphens, and cannot end with a hyphen";
    }
    return '';
};


export const validateDiskSize = (size: number, minDiskSize: number) => {
    if (size < minDiskSize || size > 250) {
        return `Disk size must be between ${minDiskSize} and 250 GB`;
    }
    return '';
};


export const validateSshKey = (key: string, os: string, family: string) => {
    if (os === 'linux' && !key) {
        return "SSH Public Key is required for Unix-based servers";
    } else if (os === 'windows' && family.includes("-core") && !key) {
        return "SSH Public Key is required for Windows Core servers";
    }
    return '';
};