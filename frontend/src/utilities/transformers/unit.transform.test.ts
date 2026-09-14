import { describe, expect, it } from "vitest";
import { transformToFullUnit } from "./unit.transform";
import { transformToCatalog, transformToSpecification } from "./specification.transform";
import { transformToSpecificationEdit } from "./specificationEdit.transform";

describe("lab rubric opt-in", () => {
    it.each([undefined, false, "true", 1])("ignores a global rubric flag when the lab setting is %s", (setting) => {
        const result = transformToFullUnit({
            unit: { id: "abcdefghij", rubric_support: setting },
            workouts: [], roster: 0, rubric_support: true,
        });
        expect(result.rubric_support).toBe(false);
    });

    it("preserves an explicit lab opt-in", () => {
        const result = transformToFullUnit({
            unit: { id: "abcdefghij", rubric_support: true },
            workouts: [], roster: 0,
        });
        expect(result.rubric_support).toBe(true);
    });

    it.each([transformToCatalog, transformToSpecification, transformToSpecificationEdit])(
        "preserves the opt-in when reading a specification", (transform) => {
            expect(transform({}).rubric_support).toBe(false);
            expect(transform({ rubric_support: true }).rubric_support).toBe(true);
        },
    );
});
