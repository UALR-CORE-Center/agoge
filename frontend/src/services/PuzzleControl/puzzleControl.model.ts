export interface LampCapability {
    type?: string;
    instance: string;
    value?: number;
}

export interface LampDevice {
    name?: string;
    sku: string;
    deviceId: string;
    capabilities?: LampCapability[] | string[];
}

export interface LampTest {
    id: string;
    title: string;
    questions: LampQuestion[];
    join_code: string;
    LampDevice?: LampDevice;
}

export interface LampQuestion {
    id?: string;
    title: string;
    answer?: string;
    fuzzy?: string;
    isCorrect?: boolean;
    hint?: string;
}

export interface GetQuestionsResponse {
    questions: LampQuestion[];
}

export interface GetTestsResponse {
    tests: LampTest[];
}

export interface LampState {
    power?: boolean;
    brightness?: number;
    colorRgb?: { r: number; g: number; b: number };
    colorTemperatureK?: number;
    raw?: any;
}