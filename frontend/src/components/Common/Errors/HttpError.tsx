export const BUILD_AVAILABILITY_REFRESH = "agoge:build-availability-refresh";

class HttpError extends Error {
    public status: number;

    constructor(status: number, message: string, public readonly code?: string) {
        super(message);
        this.status = status;
        this.name = "AgogeError";
    }
}

export default HttpError;
