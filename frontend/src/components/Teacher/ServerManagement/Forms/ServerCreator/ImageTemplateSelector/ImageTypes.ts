import {GlobalComputeImage, ImageSummary} from "../../../../../services/Server/image.model";

export interface ImageTemplateSelectorProps {
    onTemplateSelect: (os: string, diskSize: number) => void;
}

export interface SortedImageLists {
    custom: ImageSummary[];
    linux: GlobalComputeImage[];
    windows: GlobalComputeImage[];
}

export enum ImageTabs {
    CUSTOM = 'custom',
    LINUX = 'linux',
    WINDOWS = 'windows'
}