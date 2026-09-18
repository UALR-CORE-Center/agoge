type ImageArchitecture = 'X86_64' | 'ARM64';

interface ImageArchitectureSource {
    architecture?: string | null;
    self_link?: string;
    family?: string;
    base_family?: string;
    name?: string;
}

const normalize = (value?: string | null): ImageArchitecture | undefined => {
    switch (value?.trim().toUpperCase()) {
        case 'X86_64':
        case 'X86-64':
        case 'AMD64':
            return 'X86_64';
        case 'ARM64':
        case 'AARCH64':
            return 'ARM64';
        default:
            return undefined;
    }
};

export const getImageArchitecture = (image: ImageArchitectureSource): ImageArchitecture | undefined => {
    if (typeof image.architecture === 'string' && image.architecture.trim()) return normalize(image.architecture);
    // Legacy catalogs lack the field. Recognize explicit architecture tokens,
    // prioritizing the source URL, but never assume that an unknown image is x86.
    for (const value of [image.self_link, image.family, image.base_family, image.name]) {
        const token = typeof value === 'string'
            ? value.match(/(?:^|[-_/\s])(amd64|x86_64|x86-64|arm64|aarch64)(?=$|[-_/\s])/i)
            : null;
        if (token) return normalize(token[1]);
    }
    return undefined;
};

export const imageArchitectureLabel = (image: ImageArchitectureSource): string => {
    const architecture = getImageArchitecture(image);
    return architecture === 'X86_64' ? 'AMD64 (x86-64)' : architecture ?? 'Unknown';
};

export const serverImageArchitectureError = (image: ImageArchitectureSource): string => (
    getImageArchitecture(image) === 'ARM64'
        ? 'ARM64 images cannot run on the E2 machine types available in this form. Select an AMD64 (x86-64) image.'
        : ''
);
