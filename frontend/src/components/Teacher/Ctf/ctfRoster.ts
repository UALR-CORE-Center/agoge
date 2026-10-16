// Mirrors CTF_MEMBER_EMAIL_PATTERN in common/models/agoge.py; the API is the final check.
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// MAX_CTF_TEAM_MEMBERS in common/models/agoge.py.
export const MAX_TEAM_MEMBERS = 50;

export interface ParsedEmails {
    emails: string[];
    invalid: string[];
}

/** Split on commas, semicolons, whitespace or newlines; trim, lowercase and de-duplicate. */
export const parseEmails = (text: string): ParsedEmails => {
    const emails: string[] = [];
    const invalid: string[] = [];
    for (const raw of text.split(/[\s,;]+/)) {
        const email = raw.trim().toLowerCase();
        if (!email) continue;
        if (!EMAIL_PATTERN.test(email)) {
            invalid.push(raw.trim());
        } else if (!emails.includes(email)) {
            emails.push(email);
        }
    }
    return {emails, invalid};
};

export interface ParsedRoster {
    // Team name -> member emails, in first-seen order.
    teams: {team_name: string; members: string[]}[];
    // 1-based line numbers with the reason each was skipped.
    errors: string[];
}

/**
 * Parse `team,email` lines (a header row naming `team` is skipped). One line per member; lines
 * sharing a team name (case-insensitive) build one team, named as first written.
 */
export const parseRosterCsv = (text: string): ParsedRoster => {
    const teams: {team_name: string; members: string[]}[] = [];
    const errors: string[] = [];
    text.split(/\r?\n/).forEach((line, index) => {
        const trimmed = line.trim();
        if (!trimmed) return;
        const cells = trimmed.split(',').map((cell) => cell.trim().replace(/^"(.*)"$/, '$1').trim());
        if (index === 0 && cells[0]?.toLowerCase() === 'team') return;
        const [teamName, email] = cells;
        if (cells.length < 2 || !teamName || !email) {
            errors.push(`Line ${index + 1}: expected "team,email"`);
            return;
        }
        const normalized = email.toLowerCase();
        if (!EMAIL_PATTERN.test(normalized)) {
            errors.push(`Line ${index + 1}: "${email}" is not an email address`);
            return;
        }
        let team = teams.find((t) => t.team_name.toLowerCase() === teamName.toLowerCase());
        if (!team) {
            team = {team_name: teamName, members: []};
            teams.push(team);
        }
        if (!team.members.includes(normalized)) team.members.push(normalized);
    });
    for (const team of teams) {
        if (team.members.length > MAX_TEAM_MEMBERS) {
            errors.push(`Team ${team.team_name} has ${team.members.length} members; the limit is ${MAX_TEAM_MEMBERS}`);
        }
    }
    return {teams, errors};
};
