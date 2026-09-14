// Leave room for the suffixes used by template server resources.
const MAX_SERVER_NAME_LENGTH = 54;

export const localImageNameError = (
    name: string,
    sourceName: string,
    existingNames: string[] = []
): string => {
    if (!name || name.length > MAX_SERVER_NAME_LENGTH || !/^[a-z]([-a-z0-9]*[a-z0-9])?$/.test(name)) {
        return 'Use 1–54 lowercase letters, numbers, or hyphens. Start with a letter and end with a letter or number.';
    }
    if (name.startsWith('image-')) return 'Choose a name that does not start with image-.';
    if (['agoge', 'google'].includes(name)) return 'This name is reserved. Choose another name.';
    if (name === sourceName) return 'Choose a new name for your local copy.';
    if (existingNames.includes(name)) return 'An image with this name already exists. Choose another name.';
    return '';
};

export const suggestLocalImageName = (sourceName: string, existingNames: string[] = []): string => {
    let base = sourceName.toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/^-+|-+$/g, '').replace(/^(image-)+/, '');
    if (base === 'image') base = 'local-image';
    if (!/^[a-z]/.test(base)) base = `local-${base}`;
    const occupiedNames = new Set([sourceName, ...existingNames]);
    for (let index = 1; ; index += 1) {
        const suffix = index === 1 ? '-local' : `-local-${index}`;
        const name = `${base.slice(0, MAX_SERVER_NAME_LENGTH - suffix.length).replace(/-+$/g, '')}${suffix}`;
        if (!occupiedNames.has(name)) return name;
    }
};
