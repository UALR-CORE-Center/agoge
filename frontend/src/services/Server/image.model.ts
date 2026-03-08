import {HumanInteraction} from "../Specification/specification.model";

interface InitializeParams {
    diskSizeGb: number;
    sourceImage: string;
    type: string;
}

export interface ImageDisk {
    autoDelete: boolean;
    boot: boolean;
    initializeParams: InitializeParams;
}

export interface AgogeImage {
    id: string;
    add_disk: string;
    description: string;
    disks: ImageDisk[];
    dns_record: string;
    human_interaction: HumanInteraction[];
    image: string;
    in_use_by: string;
    machine_type: string;
    name: string;
    os: string;
    self_link: string;
    labels: string[];
    state: number;
    state_timestamp: string;
    status: number;
    tags: string[];
    base_family?: string;
    image_exists?: boolean;
}

export interface ImageSummary {
    name: string;
    disk_size: string;
    self_link: string;
    os: string;
    description?: string;
    base_family?: string;
}


export interface GlobalComputeImage {
    uuid: string;
    name: string;
    image: string;
    project: string;
    family: string;
    is_enabled: boolean;
    creationTimestamp: string;
    self_link: string;
    disk_size?: string;
    os?: string;
    description?: string;
}


export interface ImageSummaryLists {
    custom: ImageSummary[];
    project: GlobalComputeImage[];
}