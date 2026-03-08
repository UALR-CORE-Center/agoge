import {
    Stack, TextField, Button, Alert, CircularProgress,
    List, ListItemButton, ListItemText, Typography, Divider, ListItem,
} from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { URL_PUZZLE_PLAYER } from "../../router/urls";
import type {LampTest} from "../../services/PuzzleControl/puzzleControl.model";
import { puzzleControlService } from "../../services/PuzzleControl/puzzleControl.service";

export default function PlayerHomePage() {
    const navigate = useNavigate();

    const [loading, setLoading] = useState(false);
    const [err, setErr] = useState<string | null>(null);
    const [tests, setTests] = useState<LampTest[]>([]);
    const [selectedJoinCode, setSelectedJoinCode] = useState("");
    const [codeInput, setCodeInput] = useState("");

    const canJoin = useMemo(() => {
        const target = (selectedJoinCode || codeInput).trim();
        return target.length > 0 && !loading;
    }, [selectedJoinCode, codeInput, loading]);

    const loadTests = async () => {
        setErr(null);
        setLoading(true);
        try {
            const res = await puzzleControlService.get_tests();
            setTests(res?.tests ?? []);
        } catch (e: any) {
            setErr(e?.message ?? "Failed to load tests.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void loadTests();
    }, []);

    const handleJoin = () => {
        const target = (selectedJoinCode || codeInput).trim();
        if (!target) return;
        navigate(`${URL_PUZZLE_PLAYER}/${target}`);
    };

    return (
        <Stack spacing={2} sx={{ maxWidth: 720, mx: "auto", mt: 4 }}>
            <Typography variant="h5">Choose a puzzle</Typography>

            <Stack direction="row" spacing={2} alignItems="center">
                <Button onClick={loadTests} disabled={loading} variant="outlined">
                    {loading ? <CircularProgress size={20} /> : "Refresh list"}
                </Button>
            </Stack>

            {err && <Alert severity="error">{err}</Alert>}

            <Divider />

            <Typography variant="subtitle1">Available tests</Typography>
            {tests.length === 0 && !loading && (
                <Alert severity="info">No tests available right now.</Alert>
            )}

            <List>
                {tests.map((t) => {
                    const codeForJoin = (t.join_code).trim();
                    const isSelected = selectedJoinCode === codeForJoin;

                    return (
                        <ListItem key={t.id} disablePadding>
                            <ListItemButton
                                selected={isSelected}
                                onClick={() => {
                                    if (!codeForJoin) {
                                        console.warn("No join code or id on test:", t);
                                        return;
                                    }
                                    setSelectedJoinCode(codeForJoin);
                                }}
                            >
                                <ListItemText
                                    primary={
                                        <Typography fontWeight={isSelected ? "bold" : "normal"}>
                                            {t.title ?? `Test ${t.id}`}
                                        </Typography>
                                    }
                                    secondary={
                                        codeForJoin
                                            ? `Join code: ${codeForJoin} • ID: ${t.id}`
                                            : `ID: ${t.id}`
                                    }
                                />
                            </ListItemButton>
                        </ListItem>
                    );
                })}
            </List>

            <Divider />

            <TextField
                fullWidth
                label="Or enter a join code"
                value={codeInput}
                onChange={(e) => {
                    setSelectedJoinCode("");
                    setCodeInput(e.target.value);
                }}
                onKeyDown={(e) => e.key === "Enter" && canJoin && handleJoin()}
                disabled={loading}
                placeholder="e.g. 242907 or F7A677"
                autoComplete="one-time-code"
            />

            <Button
                variant="contained"
                size="large"
                onClick={handleJoin}
                disabled={!canJoin}
            >
                {loading ? <CircularProgress size={22} /> : "Play"}
            </Button>
        </Stack>
    );
}