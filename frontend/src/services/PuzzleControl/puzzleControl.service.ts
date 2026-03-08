import {
    URL_PUZZLE_CONTROL_API_BASE,
    URL_PUZZLE_CONTROL_QUESTION
} from "../../router/urls";
import formatString from "../../utilities/formatString";
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
        transformToPuzzleLamp
    );
};

const post_choice = async (question_id: string,answer: string) => {
    const payload = {'question_id': question_id, 'answer': answer};
    const endpoint = formatString(`${URL_PUZZLE_CONTROL_API_BASE}question/check`)
    return await apiService.post<LampQuestion>(
        endpoint,
        payload,
        false,
        transformToPuzzleQuestion
    );
};

const create_question = async (
    sku: string, device: string, title: string, answer: string, fuzzy: boolean,
) => {
    const payload = {'sku': sku, 'device': device, 'title': title, 'answer': answer, 'fuzzy': fuzzy};
    return await apiService.post<LampQuestion>(
        `${URL_PUZZLE_CONTROL_API_BASE}question`,
        payload,
        true,
        transformToPuzzleQuestion
    );
};

const create_test = async (
    sku: string, device: string, title: string, questions: LampQuestion[],
) => {
    const payload = {'title':title, 'sku': sku, 'device': device, 'questions': questions};
    return await apiService.post<LampTest>(
        `${URL_PUZZLE_CONTROL_API_BASE}test`,
        payload,
        false,
        transformToPuzzleTest
    )
}

const get_tests = async () => {
    return await apiService.get<GetTestsResponse>(
        `${URL_PUZZLE_CONTROL_API_BASE}test`,
        null,
        false,
        transformToPuzzleTests
    );
};

const get_test = async (join_code: string) => {
    return await apiService.get<LampTest>(
        `${URL_PUZZLE_CONTROL_API_BASE}test/${join_code}`,
        null,
        false,
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
        false,
        transformToPuzzleQuestion
    );
};

export const puzzleControlService = {
    create_question,
    create_test,
    get,
    post,
    post_choice,
    get_test,
    get_tests,
    check_answer,
};