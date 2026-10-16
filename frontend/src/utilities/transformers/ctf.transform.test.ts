import {describe, expect, it} from "vitest";
import {CtfEvent, CtfTeamRow, CtfTemplateRow} from "../../services/Ctf/ctf.model";
import {
    transformToCtfEvent,
    transformToCtfTeamList,
    transformToCtfTeamRow,
    transformToCtfTemplateList,
    transformToCtfTemplateRow,
} from "./ctf.transform";

describe("transformToCtfTeamRow", () => {
    it("copies the modelled keys", () => {
        const row: CtfTeamRow = {
            workout_id: "wwwwwwwwww", team_name: "Red", members: ["a@x.io"],
            workout_state: 50, workout_state_name: "RUNNING", arm_status: "armed",
        };
        expect(transformToCtfTeamRow({...row, extra: 1} as CtfTeamRow)).toEqual(row);
    });

    it("defaults missing members, nullable state fields and arm status", () => {
        const row = transformToCtfTeamRow({workout_id: "w", team_name: "Red"} as CtfTeamRow);
        expect(row).toEqual({
            workout_id: "w", team_name: "Red", members: [],
            workout_state: null, workout_state_name: null, arm_status: "pending",
        });
    });

    it("keeps a NOT_BUILT state of -1 (not coerced to null)", () => {
        const row = transformToCtfTeamRow({workout_id: "w", team_name: "R", workout_state: -1} as CtfTeamRow);
        expect(row.workout_state).toBe(-1);
    });

    it("maps a list and tolerates null", () => {
        expect(transformToCtfTeamList(null as unknown as CtfTeamRow[])).toEqual([]);
        expect(transformToCtfTeamList([{workout_id: "w", team_name: "R"} as CtfTeamRow])).toHaveLength(1);
    });
});

describe("transformToCtfTemplateRow", () => {
    it("copies keys and normalizes server fields", () => {
        const row = transformToCtfTemplateRow({
            id: "spec1", name: "Lab", ctf_name: "Spring", flag_count: 4,
            servers: [{name: "web"}],
        } as CtfTemplateRow);
        expect(row).toEqual({
            id: "spec1", name: "Lab", description: null, ctf_name: "Spring", flag_count: 4,
            servers: [{name: "web", os: null, machine_type: null}],
        });
    });

    it("defaults flag_count and servers", () => {
        const row = transformToCtfTemplateRow({id: "s", name: "L", ctf_name: "C", description: "d"} as CtfTemplateRow);
        expect(row.flag_count).toBe(0);
        expect(row.servers).toEqual([]);
        expect(row.description).toBe("d");
    });

    it("maps a list and tolerates undefined", () => {
        expect(transformToCtfTemplateList(undefined as unknown as CtfTemplateRow[])).toEqual([]);
    });
});

describe("transformToCtfEvent join_code", () => {
    const base = {
        id: "abcdefghij", unit_id: "klmnopqrst", instructor_id: [],
        spec: {name: "S", flags: [], scoring: {flag_prefix: "agoge", submission_rate_limit: 10, reveal_decoy_penalty: false}},
        seed_version: 1, creation_timestamp: 1, accumulated_pause_seconds: 0, state: 0, state_timestamp: "t",
    } as unknown as CtfEvent;

    it("keeps a join code and nulls a missing one", () => {
        expect(transformToCtfEvent({...base, join_code: "ABC123"}).join_code).toBe("ABC123");
        expect(transformToCtfEvent(base).join_code).toBeNull();
    });
});
