// @vitest-environment jsdom
import {afterEach, describe, expect, it, vi} from "vitest";

const loadAt = async (url: string) => {
    vi.resetModules();
    const location = new URL(url);
    vi.stubGlobal("location", location);
    Object.defineProperty(window, "location", {value: location, configurable: true});
    return import("./appContext");
};

describe("absoluteUrl", () => {
    const original = window.location;
    afterEach(() => {
        Object.defineProperty(window, "location", {value: original, configurable: true});
        vi.unstubAllGlobals();
    });

    it("does not double the slash on localhost", async () => {
        const {absoluteUrl} = await loadAt("http://localhost:3000/teacher/lab/abc");
        expect(absoluteUrl("/join")).toBe("http://localhost:3000/join");
        expect(absoluteUrl("join")).toBe("http://localhost:3000/join");
    });

    it("keeps the project path prefix when deployed", async () => {
        const {absoluteUrl} = await loadAt("https://app.agoge-labs.com/test-dev/teacher/lab/abc");
        expect(absoluteUrl("/join")).toBe("https://app.agoge-labs.com/test-dev/join");
    });
});
