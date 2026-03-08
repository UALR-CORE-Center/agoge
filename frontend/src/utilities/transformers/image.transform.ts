import {AgogeImage, ImageSummaryLists} from "../../services/Server/image.model"

export const transformToAgogeImage = (data: any): AgogeImage => {
    return {
        id: data.id ?? '',
        add_disk: data.add_disk,
        description: data.description,
        disks: data.disks,
        dns_record: data.dns_record,
        human_interaction: data.human_interaction,
        image: data.image,
        image_exists: data.image_exists,
        in_use_by: data.in_use_by,
        machine_type: data.machine_type,
        name: data.name,
        os: data.os,
        self_link: data.self_link,
        labels: data.labels,
        state: data.state,
        state_timestamp: data.state,
        status: data.status,
        tags: data.tags,
    };
};

export const transformToAgogeImageList = (data: any[]): AgogeImage[] =>{
    return data.map(transformToAgogeImage)
}
