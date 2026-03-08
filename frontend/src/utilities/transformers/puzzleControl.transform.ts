import {
    LampDevice,
    LampCapability,
    LampQuestion,
    GetQuestionsResponse, LampTest, GetTestsResponse
} from "../../services/PuzzleControl/puzzleControl.model";

export const transformToPuzzleLamps = (data: any): LampDevice[] => {
    const raw = Array.isArray(data?.devices) ? data.devices : Array.isArray(data) ? data : [];

    return raw.map((d: any) => ({
        name: d.deviceName ?? d.name ?? "Unknown",
        sku: d.sku,
        deviceId: d.device ?? d.deviceId,
        capabilities: (d.capabilities ?? []).map((cap: any): LampCapability => ({
            instance: cap.instance,
            type: cap.type,
            value: cap.value,
        })),
    }));
};

export const transformToPuzzleLamp = (data: any): LampDevice => {
    return {
        name: data.deviceName || data.name || "Unknown",
        sku: data.sku,
        deviceId: data.device || data.deviceId,
        capabilities: (data.capabilities || []).map((cap: any): LampCapability => ({
            instance: cap.instance,
            type: cap.type,
            value: cap.value,
        })),
    };
};

export const transformToPuzzleQuestion = (data: any): LampQuestion => {
    return {
        title: data.title,
        id: data.id,
        answer: data.answer || null,
        fuzzy: data.fuzzy || null,
        isCorrect: data.isCorrect || null,
        hint: data.hint || null,
    }
}

export const transformToPuzzleTest = (data: any): LampTest => {
    const test = data?.test ?? data;

    return {
        id: test.id,
        title: test.title,
        join_code: test.join_code,
        questions: Array.isArray(test.questions)
            ? test.questions.map(transformToPuzzleQuestion)
            : [],
        LampDevice: test.LampDevice || null,
    };
};

export const transformToPuzzleTests = (
    data: GetTestsResponse | any
): GetTestsResponse => {
    const tests = Array.isArray(data?.tests)
        ? data.tests.map(transformToPuzzleTest)
        : [];
    return {tests}
};

export const transformToPuzzleQuestions = (
    data: GetQuestionsResponse | any
): GetQuestionsResponse => {
    const questions = Array.isArray(data?.questions)
        ? data.questions.map(transformToPuzzleQuestion)
        : [];
    return { questions };
};