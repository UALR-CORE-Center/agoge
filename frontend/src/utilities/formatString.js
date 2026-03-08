function formatString(string, replacements, encode = false) {
    return string.replace(/{(\w+)}/g, (match, key) => {
        if (typeof replacements[key] !== 'undefined') {
            let replacement = replacements[key];
            if (encode) {
                replacement = encodeURIComponent(replacement);
            }
            return replacement;
        }
        return match;
    });
}

export default formatString;

export function capitalizeString (value) {
    return value.charAt(0).toUpperCase() + value.slice(1);
}
