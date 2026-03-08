import React, { useState } from 'react';
import {
    Box,
    Typography,
    TextField,
    Button,
    CircularProgress,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    useTheme
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { Workout } from '../../services/Workout/workout.model';
import { workoutService } from '../../services/Workout/workout.service';
import SimpleSnackbar from "../Common/SnackBar/SnackBar";

interface AssessmentProps {
    workout: Workout;
}

interface Question {
    id: string;
    name: string | null;
    type: string;
    question: string;
    key: string | null;
    answer: string;
    script_assessment: boolean;
    complete: boolean;
}

interface SnackbarProps {
    open: boolean;
    message: string;
    severity: 'success' | 'error'
}

const isQuestionArray = (arr: any): arr is Question[] =>
    Array.isArray(arr) && arr.every(item => typeof item.question === 'string');

const StudentAssessment: React.FC<AssessmentProps> = ({ workout }) => {
    const [questions, setQuestions] = useState<Question[]>(
        workout.assessment && isQuestionArray(workout.assessment.questions)
        ? workout.assessment.questions
        : []
    );

    const [answers, setAnswers] = useState<{ [key: string]: string }>({});
    const [loading, setLoading] = useState<{ [key: string]: boolean }>({});
    const [snackbar, setSnackbar] = useState<SnackbarProps>({
        open: false,
        message: '',
        severity: 'success'
    });
    const theme = useTheme();

    const handleAnswerChange = (questionId: string, answer: string) =>
        setAnswers(prev => ({ ...prev, [questionId]: answer }));

    const handleSubmit = async (question: Question) => {
        setLoading(prev => ({ ...prev, [question.id]: true }));

        const responseObject = {
            response: answers[question.id],
            check_auto: false
        };

        try {
            const response = await workoutService.answer_question(workout.id, question.id, JSON.stringify(responseObject));

            // Update the questions state with the new values returned from the backend
            if (response.questions && isQuestionArray(response.questions)) {
                setQuestions(response.questions);
                const updatedQuestion = response.questions.find((res: Question) => res.id === question.id);
                const isComplete = updatedQuestion?.complete;
                setSnackbar({
                    open: true,
                    message: isComplete ? 'Correct answer submitted!' : 'Answer submitted but incorrect.',
                    severity: isComplete ? 'success' : 'error'
                });
            } else {
                throw new Error('Unexpected response format');
            }
        } catch (error) {
            console.error("Error submitting answer:", error);
            setSnackbar({
                open: true,
                message: 'Error submitting answer. Please try again.',
                severity: 'error'
            });
        }

        setLoading(prev => ({ ...prev, [question.id]: false }));
    };

    const handleCloseSnackbar = () => {
        setSnackbar({ ...snackbar, open: false });
    };

    return (
        <Box component="section" aria-labelledby="assessment-h2" sx={{ p: 3, width: '100%' }}>
            <Typography id="assessment-h2" component="h2" variant="h5">
                Assessment Questions
            </Typography>
            {questions.length > 0 ? (
                questions.map((question, index) => (
                    <Box key={question.id} sx={{ mb: 2 }}>
                        <Accordion>
                            <AccordionSummary
                                expandIcon={<ExpandMoreIcon />}
                                id={`question-${question.id}-header`}
                                aria-controls={`question-${question.id}-content`}
                            >
                                <Typography
                                    id={`question-${question.id}-h3`}
                                    component="h3"
                                    variant="subtitle1"
                                    sx={{ flexGrow: 1 }}
                                >
                                    Question {index + 1}
                                </Typography>
                                {question.complete && <CheckCircleIcon sx={{ color: 'green', ml: 1 }} />}
                            </AccordionSummary>

                            <AccordionDetails
                                id={`question-${question.id}-content`}
                                aria-labelledby={`question-${question.id}-header`}
                            >
                                <Typography component="p" variant="subtitle1" sx={{ mt: 2 }}>
                                    {question.question}
                                </Typography>
                                <TextField
                                    autoComplete="off"
                                    fullWidth
                                    label={`Answer ${index + 1}`}
                                    variant="outlined"
                                    sx={{ my: 2 }}
                                    value={answers[question.id] || ''}
                                    onChange={(e) => handleAnswerChange(question.id, e.target.value)}
                                    disabled={question.complete}
                                    aria-labelledby={`question-${question.id}-h3`}
                                />
                                <Button
                                    variant="contained"
                                    onClick={() => handleSubmit(question)}
                                    disabled={loading[question.id] || question.complete}
                                >
                                    {loading[question.id] ? <CircularProgress size={24} /> : 'Submit'}
                                </Button>
                            </AccordionDetails>
                        </Accordion>
                    </Box>
                ))
            ) : (
                <Typography variant="subtitle1" sx={{ mt: 2 }}>
                    No Questions
                </Typography>
            )}
            <SimpleSnackbar
                message={snackbar.message}
                open={snackbar.open}
                onClose={handleCloseSnackbar}
                severity={snackbar.severity}
                autoHideDuration={3000}
            />
        </Box>
    );
};

export default StudentAssessment;
