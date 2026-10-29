import {URL_PUZZLE_CONTROL_API_BASE} from "../../router/urls";
import {
    transformToPuzzleLamp,
    transformToPuzzleQuestion,
    transformToPuzzleLamps, transformToPuzzleQuestions, transformToPuzzleTest, transformToPuzzleTests
} from "../../utilities/transformers/puzzleControl.transform";
import {apiService} from "../api-request.service";
import {GetQuestionsResponse, GetTestsResponse, LampDevice, LampQuestion, LampTest} from "./puzzleControl.model";

export type LampAction = [string, any];

const get = async (): Promise<LampDevice[]> => {
    return await apiService.get<LampDevice[]>(
        URL_PUZZLE_CONTROL_API_BASE,
        null,
        true,
        transformToPuzzleLamps
    );
};

const post = async (sku: string, device: string, action: LampAction) => {
    const payload = {'sku': sku, 'device': device, 'action': action};
    return await apiService.post<LampDevice>(
        `${URL_PUZZLE_CONTROL_API_BASE}control`,
        payload,
        true,
        null,
        transformToPuzzleLamp
    );
};

const create_test = async (
    sku: string, device: string, title: string, questions: LampQuestion[],
) => {
    const payload = {'title':title, 'sku': sku, 'device': device, 'questions': questions};
    return await apiService.post<LampTest>(
        `${URL_PUZZLE_CONTROL_API_BASE}test`,
        payload,
        true,
        null,
        transformToPuzzleTest
    )
}

const get_tests = async () => {
    return await apiService.get<GetTestsResponse>(
        `${URL_PUZZLE_CONTROL_API_BASE}test`,
        null,
        true,
        transformToPuzzleTests
    );
};

const get_test = async (join_code: string) => {
    return await apiService.get<LampTest>(
        `${URL_PUZZLE_CONTROL_API_BASE}test/${join_code}`,
        null,
        true,
        transformToPuzzleTest
    )
}

const check_answer = async (
    test_id: string,
    question_id: string,
    answer: string
) => {
    const payload = { test_id, question_id, answer };

    return await apiService.post<LampQuestion>(
        `${URL_PUZZLE_CONTROL_API_BASE}question/check`,
        payload,
        true,
        null,
        transformToPuzzleQuestion
    );
};

export const puzzleControlService = {
    create_test,
    get,
    post,
    get_test,
    get_tests,
    check_answer,
};