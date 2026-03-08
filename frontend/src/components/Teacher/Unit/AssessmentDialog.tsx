import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import {
    Button, Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    List,
    ListItem,
    ListItemText,
    Typography
} from "@mui/material";
import React from "react";

interface Props {
    open: boolean
    onClose: () => void;
    currentStudent: {
        student_name?: string,
        student_email?: string,
        assessment?: any
    }
}
export default function AssessmentDialog (props: Props) {
    const {open, onClose, currentStudent} = props;

    const handleCloseModal = () => {
        if (onClose) onClose();
    }

    return (
        <React.Fragment>
            <Dialog
                open={open}
                onClose={handleCloseModal}
                fullWidth
            >
                <DialogTitle>
                    Assessment for {currentStudent?.student_name || currentStudent?.student_email || "Unknown Student"}
                </DialogTitle>
                <DialogContent dividers>
                    {Array.isArray(currentStudent?.assessment?.questions) && currentStudent.assessment.questions.length > 0 ? (
                        <List>
                            {currentStudent.assessment.questions.map((question, index) => (
                                <ListItem
                                    key={index}
                                    sx={{
                                        m: 1,
                                        border: '1px solid #ccc',
                                        borderRadius: '4px',
                                        padding: '10px',
                                        display: 'flex',
                                        alignItems: 'center',
                                    }}
                                >
                                    {question.complete && (
                                        <CheckCircleIcon sx={{ color: 'green', mr: 1 }} />
                                    )}
                                    <ListItemText primary={question.question} />
                                </ListItem>
                            ))}
                        </List>
                    ) : (
                        <Typography variant="subtitle1" sx={{ mt: 2 }}>
                            No Responses
                        </Typography>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleCloseModal} color="primary" variant="contained">
                        Close
                    </Button>
                </DialogActions>
            </Dialog>
        </React.Fragment>
    );
}