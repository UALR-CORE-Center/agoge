const host = typeof window !== "undefined" ? window.location.hostname : "";
const path = typeof window !== "undefined" ? window.location.pathname : "/";

const isLocal =
    host === "localhost" ||
    host === "127.0.0.1" ||
    host.endsWith(".local");

export const PROJECT_ID = isLocal ? "" : (path.split("/")[1] || "");
export const BASENAME = PROJECT_ID ? `/${PROJECT_ID}` : "/";

export const absoluteUrl = (routePath: string) => {
    if (typeof window === "undefined") return routePath;

    const clean = routePath.startsWith("/") ? routePath : `/${routePath}`;
    return `${window.location.origin}${BASENAME}${clean}`;
};