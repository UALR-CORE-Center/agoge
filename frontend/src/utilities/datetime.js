
export function getCurrentTimestampUTC(addSeconds = 0) {
    // Ensure addSeconds is an integer; if not, default to 0
    if (isNaN(parseInt(addSeconds))) {
        addSeconds = 0;
    }

    const now = new Date();
    const utcNow = new Date(now.getTime() + now.getTimezoneOffset() * 60000);
    const newUtcTime = new Date(utcNow.getTime() + addSeconds * 1000);

    return newUtcTime.getTime() / 1000;
}

export function getUTCTimestampFromDatetime(datetimeStr, tz) {
    try {
        // Parse the datetime string into a Date object
        const localDate = new Date(datetimeStr.replace("T", " "));
        const localOffset = new Date().getTimezoneOffset() * 60000;

        // Convert to UTC
        const utcDate = new Date(localDate.getTime() + localOffset);
        return utcDate.getTime() / 1000;
    } catch (e) {
        throw new Error(`Error converting datetime: ${e}`);
    }
}
