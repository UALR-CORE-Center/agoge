// Service
import {URL_COMPUTE_SNAPSHOT_API_BASE} from "../../router/urls";
import {PubSub} from "../../types/PubSub";
import { apiService } from "../api-request.service";
import {SnapshotsModel} from "./snapshots.model";

const get = async (buildId: string): Promise<SnapshotsModel> => {
    return await apiService.get<SnapshotsModel>(
        `${URL_COMPUTE_SNAPSHOT_API_BASE}${buildId}/`,
        null,
        true
    );
}

const list = async (buildId: string, courseObject: number): Promise<SnapshotsModel[]> => {
    return await apiService.get<SnapshotsModel[]>(
        URL_COMPUTE_SNAPSHOT_API_BASE,
        {
            build_id: buildId,
            course_object: courseObject
        },
        true,
    );
}

const post = async (snapshotData: { [key: string]: any }) => {
    return await apiService.post(URL_COMPUTE_SNAPSHOT_API_BASE, snapshotData, true);
}

const put = async (
    serverId: string,
    courseObject: number,
    action: number,
    snapshotName?: string,
    buildId?: string,
) => {
    const endpoint = `${URL_COMPUTE_SNAPSHOT_API_BASE}${serverId}/`;
    const payload = {
        action: action,
        course_object: courseObject,
    };
    if (snapshotName) {
        payload['snapshot_name'] = snapshotName;
    }
    if (buildId) {
        payload['build_id'] = buildId;
    }
    return await apiService.put(endpoint, payload, true);
}

const delete_ = async (serverId: string, snapshotName: string, courseObject: number)=> {
    const endpoint =  `${URL_COMPUTE_SNAPSHOT_API_BASE}${serverId}/`;
    const body = {
        'snapshot_name': snapshotName,
        'course_object': courseObject,
        'action': PubSub.Actions.DELETE
    }
    return await apiService.put(endpoint, body, true);
}

export const snapshotService = {
    get,
    list,
    post,
    put,
    delete_
}