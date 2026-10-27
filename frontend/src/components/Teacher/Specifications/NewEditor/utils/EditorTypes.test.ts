import {describe, expect, it} from "vitest";
import {CTF_UNIT_TYPE, EDITOR_UNIT_TYPES, EditorForms} from "./EditorTypes";

describe("EditorTypes", () => {
    it("offers solo, community and ctf as editor unit types", () => {
        expect(EDITOR_UNIT_TYPES).toEqual(expect.arrayContaining(['solo', 'community', 'ctf']));
        expect(EDITOR_UNIT_TYPES).toHaveLength(3);
        expect(CTF_UNIT_TYPE).toBe('ctf');
    });

    it("places the CTF step after Servers", () => {
        const forms = Object.values(EditorForms);
        expect(forms.indexOf(EditorForms.Ctf)).toBe(forms.indexOf(EditorForms.Servers) + 1);
    });
});
