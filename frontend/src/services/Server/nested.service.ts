import axios, {AxiosProgressEvent} from "axios";
import HttpError from "../../components/Common/Errors/HttpError";
import {
    URL_COMPUTE_IMAGE_API_MACHINE_TYPES,
    URL_COMPUTE_IMAGE_API_NESTED,
    URL_COMPUTE_IMAGE_API_NESTED_BUILD,
    URL_COMPUTE_IMAGE_API_NESTED_CATALOG,
    URL_COMPUTE_IMAGE_API_NESTED_MEDIA,
    URL_COMPUTE_IMAGE_API_NESTED_MEDIA_ITEM,
} from "../../router/urls";
import formatString from "../../utilities/formatString";
import {
    toNestedImageCreateRequest,
    transformToNestedBuildStatus,
    transformToNestedIdResponse,
    transformToNestedMedia,
    transformToNestedMediaList,
    transformToNestedMediaUpload,
    transformToNestedOsCatalog,
} from "../../utilities/transformers/nested.transform";
import {ServerMachineTypes} from "../Specification/specificationEdit.model";
import { apiService } from "../api-request.service";
import {
    NestedBuildStatus,
    NestedIdResponse,
    NestedImageCreateRequest,
    NestedMedia,
    NestedMediaCreateRequest,
    NestedMediaUploadResponse,
    NestedOsCatalogEntry,
} from "./nested.model";

const mediaItem = (mediaId: string) =>
    formatString(URL_COMPUTE_IMAGE_API_NESTED_MEDIA_ITEM, {ITEM_ID: encodeURIComponent(mediaId)});

// Families that support nested virtualization, filtered by the API.
const list_machine_types = async (): Promise<ServerMachineTypes[]> => {
    return await apiService.get<ServerMachineTypes[]>(URL_COMPUTE_IMAGE_API_MACHINE_TYPES, {nested: true}, true);
};

const list_catalog = async (): Promise<NestedOsCatalogEntry[]> => {
    return await apiService.get<NestedOsCatalogEntry[]>(
        URL_COMPUTE_IMAGE_API_NESTED_CATALOG, null, true, transformToNestedOsCatalog
    );
};

const create = async (request: NestedImageCreateRequest): Promise<NestedIdResponse> => {
    return await apiService.post<NestedIdResponse>(
        URL_COMPUTE_IMAGE_API_NESTED,
        toNestedImageCreateRequest(request),
        true,
        null,
        transformToNestedIdResponse
    );
};

// Refreshes the build from the parent's guest attributes on every call, so poll it sparingly.
const get_build_status = async (imageName: string): Promise<NestedBuildStatus> => {
    const endpoint = formatString(URL_COMPUTE_IMAGE_API_NESTED_BUILD, {ITEM_ID: encodeURIComponent(imageName)});
    return await apiService.get<NestedBuildStatus>(endpoint, null, true, transformToNestedBuildStatus);
};

const create_media = async (request: NestedMediaCreateRequest): Promise<NestedMediaUploadResponse> => {
    const body: NestedMediaCreateRequest = {filename: request.filename, size_bytes: request.size_bytes};
    if (request.os_id) {
        body.os_id = request.os_id;
    }
    return await apiService.post<NestedMediaUploadResponse>(
        URL_COMPUTE_IMAGE_API_NESTED_MEDIA, body, true, null, transformToNestedMediaUpload
    );
};

const list_media = async (): Promise<NestedMedia[]> => {
    return await apiService.get<NestedMedia[]>(URL_COMPUTE_IMAGE_API_NESTED_MEDIA, null, true, transformToNestedMediaList);
};

// The API marks the medium complete only after it finds the object at the declared size.
const complete_media = async (mediaId: string): Promise<NestedMedia> => {
    return await apiService.put<NestedMedia>(mediaItem(mediaId), {}, true, transformToNestedMedia);
};

const delete_media = async (mediaId: string): Promise<NestedIdResponse> => {
    return await apiService.del<NestedIdResponse>(mediaItem(mediaId), true, transformToNestedIdResponse);
};

export interface NestedUploadOptions {
    osId?: string | null;
    onProgress?: (loaded: number, total: number) => void;
    signal?: AbortSignal;
}

const storageError = (e: unknown, step: string): HttpError => {
    if (axios.isCancel(e)) {
        return new HttpError(499, 'The upload was cancelled.');
    }
    const status = axios.isAxiosError(e) ? e.response?.status ?? 500 : 500;
    return new HttpError(status, `The upload to Cloud Storage failed while ${step} (HTTP ${status}). Try again.`);
};

// Signed URL -> resumable session -> bytes -> completion check. These requests go straight to
// Cloud Storage, so they use axios directly: the Firebase Authorization header would break the
// signature, and the session start must carry exactly the headers the URL was signed with.
const upload_media = async (file: File, options: NestedUploadOptions = {}): Promise<NestedMedia> => {
    const upload = await create_media({filename: file.name, size_bytes: file.size, os_id: options.osId});
    try {
        let sessionUri: string | undefined;
        try {
            const start = await axios.post(upload.upload_url, null, {
                headers: upload.upload_headers,
                signal: options.signal,
            });
            sessionUri = start.headers?.location;
        } catch (e) {
            throw storageError(e, 'starting the upload');
        }
        if (!sessionUri) {
            // The bucket's CORS must expose Location; without it the browser hides the session URI.
            throw new HttpError(502, 'Cloud Storage did not return an upload session. Check the media bucket CORS setup.');
        }
        try {
            await axios.put(sessionUri, file, {
                signal: options.signal,
                onUploadProgress: (event: AxiosProgressEvent) =>
                    options.onProgress?.(event.loaded, event.total ?? file.size),
            });
        } catch (e) {
            throw storageError(e, 'sending the file');
        }
    } catch (e) {
        // Best effort: an abandoned record would otherwise sit in the caller's list as incomplete.
        // The bucket's lifecycle rule removes the partial object either way.
        await delete_media(upload.media_id).catch(() => undefined);
        throw e;
    }
    // Not inside the cleanup above: once the bytes are stored, a failed check (e.g. a 503) must not
    // throw the upload away. The record stays in list_media as incomplete and complete_media retries it.
    return await complete_media(upload.media_id);
};

export const nestedService = {
    complete_media,
    create,
    create_media,
    delete_media,
    get_build_status,
    list_catalog,
    list_machine_types,
    list_media,
    upload_media,
};
