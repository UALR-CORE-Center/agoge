export interface Criteria {
    category: string;
    index: number;
    description: string;
}

export interface Rubric {
    build_id: string;
    headers: string[];
    categories: string[];
    criteria: Criteria[];
}