import EditIcon from "@mui/icons-material/Edit";
import {Box, Button, Dialog, DialogContent, DialogTitle, Divider} from "@mui/material";
import DialogActions from "@mui/material/DialogActions";
import React, {useEffect, useState} from "react";
import {Specification} from "../../../../services/Specification/specification.model";


interface Props {
    open: boolean,
    onClose?: Function,
    row: Specification | any,
}

interface InstructionsUrls {
    student?: string;
    teacher?: string;
}

export function InstructionsDialog (props: Props) {
    const {open, onClose, row} = props;
    const [instructionUrls, setInstructionUrls] = useState<InstructionsUrls>({});
    const teacherInstruction = row?.teacher_instruction || row.summary?.teacher_instructions_url;
    const studentInstruction = row?.student_instruction || row.summary?.student_instructions_url;

    useEffect(() => {
        if ((teacherInstruction && teacherInstruction.trim()) || (studentInstruction && studentInstruction.trim())) {
            setInstructionUrls({
                teacher: teacherInstruction,
                student: studentInstruction
            });
        } else {
            console.error("No instructions available");
        }
    }, [row, studentInstruction, teacherInstruction]);

    const openInstruction = (instruction: string | undefined) => {
        if (instruction === undefined) return;

        // This is to allow old instructions that teachers made open to a new url still work
        if (instruction.includes('http') || instruction.includes('.')) {
            window.open(instruction, '_blank');
        } else {
            // Opens to new markdown editor while keeping the correct project id
            const parts = window.location.pathname.split('/').filter(Boolean);
            const teacherIndex = parts.indexOf('teacher');
            const prefix = teacherIndex > 0 ? `/${parts[0]}` : '';
            window.open(`${prefix}/documents/edit/${instruction}`, '_blank');
        }
    };
    
    return (
        <React.Fragment>
            <Dialog
                open={open}
                onClose={onClose}
            >
                <DialogTitle>
                    View Instructions
                    <Divider sx={{ mt: 1 }}/>
                </DialogTitle>
                <DialogContent>
                    <Box sx={{ display: 'flex', flexDirection: 'row', gap: 3 }}>
                        {instructionUrls.teacher && (
                            <Button
                                endIcon={<EditIcon />}
                                variant="contained"
                                color="success"
                                onClick={() => openInstruction(instructionUrls.teacher)}
                            >
                                Teacher Instructions
                            </Button>
                        )}
                        {instructionUrls.student && (
                            <Button
                                endIcon={<EditIcon />}
                                variant="contained"
                                color="success"
                                onClick={() => openInstruction(instructionUrls.student)}
                            >
                                Student Instructions
                            </Button>
                        )}
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button
                        onClick={onClose}
                        variant="contained"
                        color="primary"
                    >
                        Close
                    </Button>
                </DialogActions>
            </Dialog>
        </React.Fragment>
    )
}