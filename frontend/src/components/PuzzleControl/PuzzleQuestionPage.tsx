import {
    Button,
    CircularProgress,
    Skeleton,
    Stack,
    TextField,
    Typography,
    Alert,
    Dialog,
    DialogTitle,
    DialogContent,
    Snackbar,
} from "@mui/material";
import DialogActions from "@mui/material/DialogActions";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
    LampDevice,
    LampTest,
} from "../../services/PuzzleControl/puzzleControl.model";
import { puzzleControlService } from "../../services/PuzzleControl/puzzleControl.service";

export default function PuzzleQuestionPage() {
    const { join_code } = useParams();
    const [test, setTest] = useState<LampTest | null>(null);
    const [answers, setAnswers] = useState<Record<string, string>>({});
    const [completed, setCompleted] = useState<Record<string, boolean>>({});
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<boolean | undefined>(undefined);
    const [showAlert, setShowAlert] = useState<boolean>(false);
    const [availableLamps, setAvailableLamps] = useState<LampDevice[]>([]);
    const [selectedLamp, setSelectedLamp] = useState<LampDevice | null>(null);
    const [loadingLamps, setLoadingLamps] = useState(false);
    const [showLampModal, setShowLampModal] = useState(true);

    // Ensure we do nothing without a lamp
    const requireLamp = () => {
        if (!selectedLamp) {
            console.warn("Lamp not selected yet.");
            return null;
        }
        return selectedLamp;
    };

    const handleResult = async (isCorrect: boolean, qid: string) => {
        const lamp = requireLamp();
        if (!lamp) return;

        setResult(isCorrect);
        setShowAlert(true);

        if (isCorrect && !completed[qid]) {
            setCompleted((prev) => ({ ...prev, [qid]: true }));
        }

        const total = test?.questions?.length ?? 0;
        if (!total) return;

        const updatedCompleted = {
            ...completed,
            ...(isCorrect ? { [qid]: true } : {}),
        };
        const completedCount = Object.values(updatedCompleted).filter(Boolean).length;

        if (isCorrect && completedCount === 1) {
            await puzzleControlService.post(lamp.sku, lamp.deviceId, [
                "switchColor",
                [0, 255, 0],
            ]);
        }

        const brightness = Math.max(
            1,
            Math.min(100, Math.round((completedCount / total) * 100))
        );

        await puzzleControlService.post(lamp.sku, lamp.deviceId, [
            "brightness",
            brightness,
        ]);

        if (completedCount === total) {
            await puzzleControlService.post(lamp.sku, lamp.deviceId, [
                "brightness",
                100,
            ]);

            await puzzleControlService.post(lamp.sku, lamp.deviceId, [
                "lightScene",
                18292,
            ]);
        }
    };

    const handleSubmit = async (qid: string) => {
        if (!test) return;
        const submitted = (answers[qid] ?? "").trim();

        const response = await puzzleControlService.check_answer(
            test.id,
            qid,
            submitted
        );
        if (response) handleResult(!!response.isCorrect, qid);
    };

    useEffect(() => {
        if (!join_code) return;
        setLoading(true);

        const fetchTest = async () => {
            try {
                const fetchedTest = await puzzleControlService.get_test(join_code);
                setTest(fetchedTest);
            } catch (e) {
                console.error("Failed to load test", e);
            } finally {
                setLoading(false);
            }
        };

        fetchTest();
    }, [join_code]);

    useEffect(() => {
        if (!test || !selectedLamp) return;

        const setWaitingState = async () => {
            try {
                await puzzleControlService.post(selectedLamp.sku, selectedLamp.deviceId, [
                    "lightScene",
                    16303,
                ]);
                await puzzleControlService.post(selectedLamp.sku, selectedLamp.deviceId, [
                    "brightness",
                    50,
                ]);
            } catch (err) {
                console.error("Failed initial lamp update:", err);
            }
        };

        setWaitingState();
    }, [test, selectedLamp]);

    // fetch available lamps for modal
    useEffect(() => {
        const fetchLamps = async () => {
            setLoadingLamps(true);
            try {
                const lamps = await puzzleControlService.get();
                setAvailableLamps(lamps);
            } catch (err) {
                console.error("Failed to load lamps:", err);
            } finally {
                setLoadingLamps(false);
            }
        };

        fetchLamps();
    }, []);

    const LampSelectionModal = (
        <Dialog open={showLampModal} fullWidth maxWidth="sm">
            <DialogTitle>Select a lamp</DialogTitle>
            <DialogContent sx={{ mt: 1, pb: 2 }}>
                {loadingLamps ? (
                    <Stack spacing={2} alignItems="center" sx={{ py: 4 }}>
                        <CircularProgress />
                        <Typography>Loading devices...</Typography>
                    </Stack>
                ) : availableLamps.length === 0 ? (
                    <Alert severity="error">No lamps found.</Alert>
                ) : (
                    <Stack spacing={2}>
                        {availableLamps.map((lamp) => (
                            <Button
                                key={lamp.deviceId}
                                variant={
                                    selectedLamp?.deviceId === lamp.deviceId ? "contained" : "outlined"
                                }
                                onClick={() => setSelectedLamp(lamp)}
                            >
                                {lamp.name} (SKU: {lamp.sku})
                            </Button>
                        ))}
                    </Stack>
                )}
            </DialogContent>
            <DialogActions>
                <Button
                    disabled={!selectedLamp}
                    variant="contained"
                    onClick={() => setShowLampModal(false)}
                >
                    Use this lamp
                </Button>
            </DialogActions>
        </Dialog>
    );

    if (loading) {
        return (
            <Stack spacing={3} sx={{ maxWidth: 720, mx: "auto", mt: 4 }}>
                <Skeleton variant="text" width={280} height={48} />
                <Skeleton variant="rectangular" height={56} />
                <Skeleton variant="rectangular" height={56} width={160} />
            </Stack>
        );
    }

    if (!test) {
        return (
            <Stack spacing={2} sx={{ maxWidth: 720, mx: "auto", mt: 4 }}>
                <Alert severity="error">Unable to load test.</Alert>
            </Stack>
        );
    }

    return (
        <>
            {LampSelectionModal}

            {!showLampModal && selectedLamp && (
                <Stack spacing={3} sx={{ maxWidth: 720, mx: "auto", mt: 4 }}>
                    <Typography variant="h4">{test.title}</Typography>
                    {test.questions.map((q, i) => {
                        const qid = q.id || String(i);
                        const isDone = !!completed[qid];

                        return (
                            <Stack
                                key={qid}
                                spacing={1.5}
                                sx={{
                                    p: 2,
                                    borderRadius: 2,
                                    border: "1px solid",
                                    borderColor: isDone ? "success.light" : "divider",
                                    bgcolor: isDone ? "success.light" : "background.paper",
                                }}
                            >
                                <Typography variant="h6">
                                    {q.title}
                                </Typography>

                                {q.hint && (
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            color: "text.secondary",
                                            fontStyle: "italic",
                                            marginBottom: 1.5,
                                        }}
                                    >
                                        Hint:{q.hint}
                                    </Typography>
                                )}

                                <TextField
                                    type="password"
                                    fullWidth
                                    label="Your Answer"
                                    value={answers[qid] ?? ""}
                                    disabled={isDone}
                                    onChange={(e) =>
                                        setAnswers((prev) => ({ ...prev, [qid]: e.target.value }))
                                    }
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter" && !isDone) handleSubmit(qid);
                                    }}
                                />

                                <Button
                                    variant="contained"
                                    color={isDone ? "success" : "primary"}
                                    disabled={isDone}
                                    onClick={() => handleSubmit(qid)}
                                >
                                    {isDone ? "Completed" : "Submit"}
                                </Button>
                            </Stack>
                        );
                    })}

                    <Snackbar
                        open={showAlert}
                        autoHideDuration={3000}
                        onClose={() => setShowAlert(false)}
                        anchorOrigin={{ vertical: "top", horizontal: "center" }}
                    >
                        <Alert
                            severity={result ? "success" : "error"}
                            onClose={() => setShowAlert(false)}
                        >
                            {result ? "Correct!" : "Incorrect — try again!"}
                        </Alert>
                    </Snackbar>
                </Stack>
            )}
        </>
    );
}