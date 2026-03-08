export interface SnapshotModel {
    name: string;
    creation_timestamp: number;
    source: string;
    type_?: string;
}

export interface SnapshotsModel {
    server_id: string;
    parent_build_id?: string;
    expiration_date?: number;
    snapshots?: SnapshotModel[]
}