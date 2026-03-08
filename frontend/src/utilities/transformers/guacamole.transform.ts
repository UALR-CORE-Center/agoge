import { GuacamoleSessionType } from "../../services/Guacamole/guacamole.model"

export const transformToGuacamoleSession = (data: any): GuacamoleSessionType => {
    return {
        url: data.url,
        token: data.token,
        protocol: data.protocol,
        hostname: data.hostname,
        server: data.server
    };
};
