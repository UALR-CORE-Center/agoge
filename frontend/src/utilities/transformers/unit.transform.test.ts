import { describe, expect, it } from "vitest";
import { transformToCatalog, transformToSpecification } from "./specification.transform";
import { transformToSpecificationEdit } from "./specificationEdit.transform";
import { transformToFullUnit } from "./unit.transform";

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

describe("specification accessibility features", () => {
    it.each([transformToCatalog, transformToSpecification])(
        "reads accessibility_features from its own field, not workout_duration_days", (transform) => {
            const result = transform({ workout_duration_days: 7, accessibility_features: false });
            expect(result.accessibility_features).toBe(false);
            expect(transform({ accessibility_features: true }).accessibility_features).toBe(true);
        },
    );
});

describe("unit CTF capability", () => {
    it.each([undefined, null, "yes", true])("is not CTF-capable when ctf is %s", (ctf) => {
        const result = transformToFullUnit({ unit: { id: "abcdefghij", ctf }, workouts: [], roster: 0 });
        expect(result.ctf_capable).toBe(false);
    });

    it("is CTF-capable when the unit carries a ctf block", () => {
        const result = transformToFullUnit({
            unit: { id: "abcdefghij", ctf: { flags: [] } }, workouts: [], roster: 0,
        });
        expect(result.ctf_capable).toBe(true);
    });
});
