import {describe, expect, it} from "vitest";
import {MAX_TEAM_MEMBERS, parseEmails, parseRosterCsv} from "./ctfRoster";

describe("parseEmails", () => {
    it("splits on commas, semicolons, spaces and newlines, lowercasing and trimming", () => {
        const result = parseEmails("Ana@Example.edu, ben@example.edu;\n  cy@example.edu\tdee@example.edu");
        expect(result.emails).toEqual(["ana@example.edu", "ben@example.edu", "cy@example.edu", "dee@example.edu"]);
        expect(result.invalid).toEqual([]);
    });

    it("de-duplicates case-insensitively, keeping first-seen order", () => {
        expect(parseEmails("a@x.io, B@x.io, A@X.IO").emails).toEqual(["a@x.io", "b@x.io"]);
    });

    it("reports invalid entries with their original casing and keeps the valid ones", () => {
        const result = parseEmails("ok@x.io, NotAnEmail, a@b, @x.io, two@@x.io");
        expect(result.emails).toEqual(["ok@x.io"]);
        expect(result.invalid).toEqual(["NotAnEmail", "a@b", "@x.io", "two@@x.io"]);
    });

    it("returns nothing for empty or separator-only input", () => {
        expect(parseEmails("")).toEqual({emails: [], invalid: []});
        expect(parseEmails(" ,; \n ")).toEqual({emails: [], invalid: []});
    });
});

describe("parseRosterCsv", () => {
    it("groups lines by team name case-insensitively, named as first written", () => {
        const result = parseRosterCsv("Red Team,ana@x.io\nblue,cy@x.io\nRED TEAM,Ben@X.io");
        expect(result.errors).toEqual([]);
        expect(result.teams).toEqual([
            {team_name: "Red Team", members: ["ana@x.io", "ben@x.io"]},
            {team_name: "blue", members: ["cy@x.io"]},
        ]);
    });

    it("skips a header row naming team, but only on the first line", () => {
        const result = parseRosterCsv("Team,Email\nRed,a@x.io");
        expect(result.teams).toEqual([{team_name: "Red", members: ["a@x.io"]}]);
        expect(result.errors).toEqual([]);

        const later = parseRosterCsv("Red,a@x.io\nteam,b@x.io");
        expect(later.teams.map((t) => t.team_name)).toEqual(["Red", "team"]);
    });

    it("handles CRLF, blank lines and quoted cells", () => {
        const result = parseRosterCsv('"Red Team","a@x.io"\r\n\r\n  \r\n"Red Team", b@x.io \r\n');
        expect(result.errors).toEqual([]);
        expect(result.teams).toEqual([{team_name: "Red Team", members: ["a@x.io", "b@x.io"]}]);
    });

    it("drops duplicate members within a team", () => {
        const result = parseRosterCsv("Red,a@x.io\nRed,A@x.io");
        expect(result.teams[0].members).toEqual(["a@x.io"]);
    });

    it("reports malformed lines with 1-based numbers and keeps parsing", () => {
        const result = parseRosterCsv("Red,a@x.io\njustone\n,b@x.io\nBlue,\nBlue,nope\nBlue,c@x.io");
        expect(result.errors).toEqual([
            'Line 2: expected "team,email"',
            'Line 3: expected "team,email"',
            'Line 4: expected "team,email"',
            'Line 5: "nope" is not an email address',
        ]);
        expect(result.teams).toEqual([
            {team_name: "Red", members: ["a@x.io"]},
            {team_name: "Blue", members: ["c@x.io"]},
        ]);
    });

    it("flags a team over the member limit but accepts exactly the limit", () => {
        const lines = (n: number) => Array.from({length: n}, (_v, i) => `Big,u${i}@x.io`).join("\n");
        expect(parseRosterCsv(lines(MAX_TEAM_MEMBERS)).errors).toEqual([]);
        expect(parseRosterCsv(lines(MAX_TEAM_MEMBERS + 1)).errors).toEqual([
            `Team Big has ${MAX_TEAM_MEMBERS + 1} members; the limit is ${MAX_TEAM_MEMBERS}`,
        ]);
    });

    it("returns empty results for empty input", () => {
        expect(parseRosterCsv("")).toEqual({teams: [], errors: []});
    });
});
