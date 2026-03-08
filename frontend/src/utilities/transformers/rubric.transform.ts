import { Rubric,Criteria } from "../../services/Rubric/rubric.model";

export const transformToRubric = (data: any): Rubric => {
    return {
        build_id: data.build_id,
        headers: data.headers,
        categories: data.categories,
        criteria: data.criteria,
    };
};