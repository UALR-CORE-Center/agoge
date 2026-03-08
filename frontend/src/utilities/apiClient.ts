import { PROJECT_ID } from "./appContext";

const ORIGIN = (import.meta.env.VITE_AGOGE_API_URL ?? "").replace(/\/+$/, "");

export const API_BASE = PROJECT_ID
    ? `${ORIGIN}/${PROJECT_ID}/`
    : `${ORIGIN}/`;

export const apiUrl = (path: string) => `${API_BASE}${path.replace(/^\/+/, "")}`;