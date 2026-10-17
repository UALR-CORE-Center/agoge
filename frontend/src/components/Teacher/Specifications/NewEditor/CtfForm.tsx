import {Alert, Stack} from "@mui/material";
import React from "react";
import {CtfSpec} from "../../../../services/Ctf/ctf.model";
import {CtfSpecFields, ctfSpecProblems} from "../../Ctf/CtfSpecEditor";

interface Props {
    value: CtfSpec;
    onChange: (spec: CtfSpec) => void;
    serverNames: string[];
    disableForm: boolean;
}

const CtfForm: React.FC<Props> = ({value, onChange, serverNames, disableForm}) => {
    const problems = ctfSpecProblems(value, serverNames);

    return (
        <Stack gap={2} sx={{pt: 1}}>
            <Alert severity="info">
                These settings become the template&apos;s CTF block. Each CTF event created from this template
                copies them, so later edits here do not change events that already exist.
            </Alert>
            {serverNames.length === 0 && (
                <Alert severity="warning">Add a server in the Servers step before adding flags.</Alert>
            )}
            <CtfSpecFields value={value} onChange={onChange} serverNames={serverNames} editable={!disableForm} />
            {problems.length > 0 && (
                <Alert severity="warning">{problems.map((problem) => <div key={problem}>{problem}</div>)}</Alert>
            )}
        </Stack>
    );
};

export default CtfForm;
