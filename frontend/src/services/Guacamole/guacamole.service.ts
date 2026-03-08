import {URL_GUACAMOLE_API_SESSION} from "../../router/urls";
import formatString from "../../utilities/formatString";
import {transformToGuacamoleSession} from "../../utilities/transformers/guacamole.transform";
import { apiService } from "../api-request.service";
import {GuacamoleSessionType} from "./guacamole.model";

const tokenizedUrl = (session: GuacamoleSessionType) => {
    const url = new URL(session.url);

    url.searchParams.set('token', session.token);

    return url.toString();
};

const getSession = async (
    buildId: string | undefined,
    serverIdx: string | undefined
): Promise<GuacamoleSessionType> => {
    const endpoint = formatString(
        URL_GUACAMOLE_API_SESSION,
        { 'BUILD_ID': buildId, 'SERVER_IDX': serverIdx }
    );
    try {
        const response = await apiService.get<GuacamoleSessionType>(
            endpoint,
            null,
            false,
            transformToGuacamoleSession
        );

        if (!response || !response.token) {
            throw new Error('Invalid session response');
        }

        return response;
    } catch (error) {
        if (error instanceof Error) {
            throw new Error(`Failed to fetch auth token: ${error.message}`);
        } else {
            throw new Error('Failed to fetch auth token: An unknown error occurred');
        }
    }
};

export const guacamoleService = {
    getSession,
    tokenizedUrl
};