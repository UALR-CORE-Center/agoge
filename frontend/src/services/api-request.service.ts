import axios from 'axios';
import {auth} from "../components/AgogeAuth/Firebase/firebaseConfig";
import HttpError, {BUILD_AVAILABILITY_REFRESH} from "../components/Common/Errors/HttpError";
import {apiUrl} from "../utilities/apiClient";

const generateHeader = async (
    includeAuth: boolean,
    headerOverrides: Record<string, string> | null = null
): Promise<object> => {
    let headers: object = {
        'Content-Type': 'application/json'
    };

    if (includeAuth) {
        const token = await auth.currentUser?.getIdToken();
        headers = {
            ...headers,
            'Authorization': `Bearer ${token}`
        };
    }

    if (headerOverrides) {
        headers = { ...headers, ...headerOverrides };
    }

    return headers;
};

const handleError = (e: any) => {
    const status = e.response?.status || 500;
    const detail = e.response?.data?.detail;
    const message = typeof detail === 'string' ? detail : detail?.message || "An error occurred";
    const code = typeof detail?.code === 'string' ? detail.code : undefined;
    if (code === 'build_quota_hold') {
        window.dispatchEvent(new Event(BUILD_AVAILABILITY_REFRESH));
    }
    throw new HttpError(status, message, code);
};

const get = async <T>(
    endpoint: string,
    params: any | null = null,
    includeAuth: boolean = true,
    transformFn?: (data: any) => T
): Promise<T> => {
    try {
        const response = await axios.get(apiUrl(endpoint), {
            headers: await generateHeader(includeAuth),
            params: params
        });
        let responseData = response.data;
        if (responseData.data && responseData.data.items) {
            responseData = responseData.data.items;
        } else if (responseData.data) {
            responseData = responseData.data;
        }
        return transformFn ? transformFn(responseData) : responseData;

    } catch (e: any) {
        throw handleError(e);
    }
};

const post = async <T>(
    endpoint: string,
    body: any,
    includeAuth: boolean = true,
    headers: Record<string, string> | null = null,
    transformFn?: (data: any) => T
): Promise<T> => {
    try {
        const response = await axios.post(
            apiUrl(endpoint),
            body,
            {headers: await generateHeader(includeAuth, headers)}
        );

        // Extract nested data.items if present
        let responseData = response.data;
        if (responseData.data && responseData.data.items) {
            responseData = responseData.data.items;
        } else if (responseData.data) {
            responseData = responseData.data;
        }
        return transformFn ? transformFn(responseData) : responseData;
    } catch (e: any) {
        throw handleError(e);
    }
};

const put = async <T>(
    endpoint: string,
    body: any,
    includeAuth: boolean = true,
    transformFn?: (data: any) => T
): Promise<T> => {
    try {
        const response = await axios.put(apiUrl(endpoint), body, {
            headers: await generateHeader(includeAuth)
        });

        // Extract nested data.items if present
        let responseData = response.data;
        if (responseData.data && responseData.data.items) {
            responseData = responseData.data.items;
        } else if (responseData.data) {
            responseData = responseData.data;
        }
        return transformFn ? transformFn(responseData) : responseData;
    } catch (e: any) {
        throw handleError(e);
    }
};

const del = async <T>(
    endpoint: string,
    includeAuth: boolean = true,
    transformFn?: (data: any) => T
): Promise<T> => {
    try {
        const response = await axios.delete(apiUrl(endpoint), {
            headers: await generateHeader(includeAuth)
        });

        // Extract nested data.items if present
        let responseData = response.data;
        if (responseData.data && responseData.data.items) {
            responseData = responseData.data.items;
        } else if (responseData.data) {
            responseData = responseData.data;
        }

        return transformFn ? transformFn(responseData) : responseData;
    } catch (e: any) {
        throw handleError(e);
    }
};

const patch = async <T>(
    endpoint: string,
    body: any,
    includeAuth: boolean = true,
    transformFn?: (data: any) => T
): Promise<T> => {
    try {
        const response = await axios.patch(apiUrl(endpoint), body, {
            headers: await generateHeader(includeAuth)
        });

        // Extract nested data.items if present
        let responseData = response.data;
        if (responseData.data && responseData.data.items) {
            responseData = responseData.data.items;
        } else if (responseData.data) {
            responseData = responseData.data;
        }
        return transformFn ? transformFn(responseData) : responseData;
    } catch (e: any) {
        throw handleError(e);
    }
};

export const apiService = { get, post, put, del, patch };
