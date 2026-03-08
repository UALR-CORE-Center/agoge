import {CancelOutlined, CheckCircleOutline, Close} from "@mui/icons-material";
import {
    Stack,
    TextField,
    Switch,
    FormControlLabel,
    Button,
    Alert,
    Typography,
    Divider,
    CircularProgress,
    Autocomplete,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Slider, Dialog, DialogTitle, IconButton, DialogContent
} from "@mui/material";
import DialogActions from "@mui/material/DialogActions";
import { useEffect, useMemo, useState } from "react";
import {LampCapability, LampDevice, LampQuestion} from "../../services/PuzzleControl/puzzleControl.model";
import { puzzleControlService } from "../../services/PuzzleControl/puzzleControl.service";

const MUSIC_MODE_OPTIONS = [
    { label: "Rhythm", value: 3 },
    { label: "Spectrum", value: 4 },
    { label: "Energetic", value: 5 },
    { label: "Rolling", value: 6 },
];

const DYNAMIC_SCENE_OPTIONS = [
    { label: "Aurora", paramId: 26433, id: 16288 },
    { label: "Sunrise", paramId: 26431, id: 16286 },
    { label: "Ocean", paramId: 26428, id: 16283 },
    { label: "Firefly", paramId: 26434, id: 16289 },
    { label: "Rainbow", paramId: 26426, id: 16281 },
    { label: "Fire", paramId: 26430, id: 16285 },
    { label: "Desert", paramId: 26437, id: 16292 },
    { label: "Night Light", paramId: 28439, id: 18276 },
    { label: "Dreamland", paramId: 28444, id: 18281 },
    { label: "Forest", paramId: 26427, id: 16282 },
    { label: "Snow flake", paramId: 26448, id: 16303 },
    { label: "Valentine’s Day", paramId: 26453, id: 16308 },
    { label: "Christmas Tree", paramId: 26452, id: 16307 },
    { label: "Party", paramId: 28456, id: 18292 },
    { label: "Dance Party", paramId: 28457, id: 18293 },
    { label: "Mars", paramId: 28486, id: 18322 },
    { label: "Moonlight", paramId: 26456, id: 16311 },
    { label: "Milky Way", paramId: 28491, id: 18327 },
];

export default function PuzzleAdminPanel() {
    const [fuzzy, setFuzzy] = useState(true);
    const [questionTitle, setQuestionTitle] = useState("");
    const [questionAnswer, setQuestionAnswer] = useState("");
    const [questionHint, setQuestionHint] = useState("");
    const [testTitle, setTestTitle] = useState("");
    const [questions, setQuestions] = useState<LampQuestion[]>([]);

    const [lamps, setLamps] = useState<LampDevice[] | null>(null);
    const [loading, setLoading] = useState(false);
    const [lampsErr, setLampsErr] = useState<string | null>(null);
    const [selectedLamp, setSelectedLamp] = useState<LampDevice | null>(null);
    const [generatedCode, setGeneratedCode] = useState<string | null>(null);
    const [selectedScene, setSelectedScene] = useState<{ label: string; paramId: number; id: number } | null>(null);
    const [brightness, setBrightness] = useState<number>(100);
    const [musicMode, setMusicMode] = useState<number | "">("");
    const [deviceControlOpen, setDeviceControlOpen] = useState(false);
    const [controlLamp, setControlLamp] = useState<LampDevice | null>(null);

    const valid = useMemo(
        () => questionTitle.trim().length > 0 && questionAnswer.trim().length > 0 && !!selectedLamp,
        [questionTitle, questionAnswer, selectedLamp]
    );

    const loadLamps = async () => {
        setLampsErr(null);
        setLoading(true);
        try {
            const list = await puzzleControlService.get();
            setLamps(list);
            if (selectedLamp && !list.find(d => d.deviceId === selectedLamp.deviceId && d.sku === selectedLamp.sku)) {
                setSelectedLamp(null);
            }
        } catch (e: any) {
            setLampsErr(e?.message ?? "Failed to load lamps.");
        } finally {
            setLoading(false);
        }
    };

    const handleAddQuestion = () => {
        if (!questionTitle.trim() || !questionAnswer.trim()) return;

        const newQuestion: LampQuestion = {
            title: questionTitle.trim(),
            answer: questionAnswer.trim(),
            fuzzy: fuzzy ? "true" : "false",
            hint: questionHint.trim(),
        };

        setQuestions(prev => [...prev, newQuestion]);
        setQuestionTitle("");
        setQuestionAnswer("");
        setQuestionHint("");
    };

    const handleRemoveQuestion = (index: number) => {
        setQuestions(prev => prev.filter((_, i) => i !== index));
    };

    const createTest = async (controlledDevice: LampDevice) => {
        try {
            const response = await puzzleControlService.create_test(
                controlledDevice.sku,
                controlledDevice.deviceId,
                testTitle,
                questions
            );
            if (response.join_code) {
                setGeneratedCode(response?.join_code);
            }
        } catch (e: any) {
            console.error(e);
        }
    };

    useEffect(() => {
        void loadLamps();
    }, []);

    useEffect(() => {
        if (!selectedLamp) return;

        const caps = Array.isArray(selectedLamp.capabilities)
            ? selectedLamp.capabilities
            : [];

        const b = caps
            .filter((c): c is LampCapability => typeof c === "object" && c !== null && "instance" in c && "type" in c)
            .find(c => c.instance === "brightness" && c.type === "devices.capabilities.range")
            ?.value;

        if (typeof b === "number") {
            setBrightness(Math.max(1, Math.min(100, b)));
        }
    }, [selectedLamp]);

    return (
        <Stack spacing={2} sx={{ maxWidth: 720, mx: "auto", mt: 4 }}>
            <Typography variant="h5">Create puzzle</Typography>
            <TextField
                label="Test Title"
                value={testTitle}
                onChange={(e) => setTestTitle(e.target.value)}
                fullWidth
                sx={{ mb: 2 }}
            />
            <Stack spacing={2}>
                {questions.length === 0 ? (
                    <Typography color="text.secondary">No questions created yet</Typography>
                ) : (
                    questions.map((q, i) => (
                        <Stack
                            key={i}
                            direction="row"
                            justifyContent="space-between"
                            alignItems="center"
                            sx={{
                                p: 1.5,
                                borderRadius: 2,
                                bgcolor: "background.paper",
                                boxShadow: 1,
                            }}
                        >
                            <Stack spacing={0.5}>
                                <Typography fontWeight="bold">{q.title}</Typography>
                                <Typography variant="body2" color="text.secondary">
                                    Answer: {q.answer}
                                </Typography>
                                {q.hint &&
                                    <Typography variant="body2" color="text.secondary">
                                    Hint: {q.hint}
                                    </Typography>
                                }
                            </Stack>

                            <Stack direction="row" alignItems="center" spacing={1}>
                                <Typography variant="body2" color="text.secondary">
                                    Fuzzy:
                                </Typography>
                                {q.fuzzy === "true" ? (
                                    <CheckCircleOutline color="success" fontSize="small" />
                                ) : (
                                    <CancelOutlined color="error" fontSize="small" />
                                )}
                                <Button
                                    variant="outlined"
                                    color="error"
                                    size="small"
                                    onClick={() => handleRemoveQuestion(i)}
                                >
                                    Remove
                                </Button>
                            </Stack>
                        </Stack>
                    ))
                )}
            </Stack>

            <Divider />

            <Stack spacing={2} sx={{mx: "auto"}}>
                <TextField
                    label="Question"
                    value={questionTitle}
                    onChange={(e) => setQuestionTitle(e.target.value)}
                    fullWidth
                />
                <TextField
                    label="Answer"
                    value={questionAnswer}
                    onChange={(e) => setQuestionAnswer(e.target.value)}
                    fullWidth
                />
                <TextField
                    label="Hint"
                    value={questionHint}
                    onChange={(e) => setQuestionHint(e.target.value)}
                    fullWidth
                />
                <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
                    <FormControlLabel
                        control={<Switch checked={fuzzy} onChange={(e) => setFuzzy(e.target.checked)} />}
                        label="Fuzzy match (handles minor typos)"
                    />
                    <Button
                        variant="contained"
                        size="small"
                        onClick={handleAddQuestion}
                        color="info"
                        sx={{ textTransform: "none", borderRadius: 3, px: 2 }}
                    >
                        + Add Question
                    </Button>
                </Stack>
            </Stack>

            <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
                <Autocomplete<LampDevice>
                    options={lamps ?? []}
                    loading={loading}
                    getOptionLabel={(d) => d?.name ?? ""}
                    value={selectedLamp}
                    onChange={(_, v) => setSelectedLamp(v)}
                    isOptionEqualToValue={(o, v) => o.deviceId === v.deviceId && o.sku === v.sku}
                    renderInput={(params) => (
                        <TextField
                            {...params}
                            label="Link to device"
                            placeholder="Pick a lamp"
                            helperText={
                                selectedLamp ? `SKU: ${selectedLamp.sku} • ID: ${selectedLamp.deviceId}` : "Choose a device to link with this question"
                            }
                            fullWidth
                        />
                    )}
                    sx={{ flex: 1 }}
                />

                <Button variant="outlined" onClick={loadLamps} disabled={loading}>
                    {loading ? <CircularProgress size={20} /> : "Refresh devices"}
                </Button>
            </Stack>

            <Stack spacing={2} sx={{ mt: 2 }}>
                <Button
                    fullWidth
                    variant="contained"
                    color="primary"
                    disabled={!selectedLamp || !testTitle || questions.length === 0}
                    onClick={() => {
                        if (selectedLamp) createTest(selectedLamp);
                    }}
                    sx={{
                        py: 1.2,
                        borderRadius: 2,
                        textTransform: "none",
                        fontWeight: 600,
                        boxShadow: 2,
                    }}
                >
                    Create Test
                </Button>
            </Stack>

            {!valid && <Alert severity="info">Add a question, answer, and pick a device to enable Start.</Alert>}
            {lamps && lamps.length === 0 && <Alert severity="info">No devices found for this account.</Alert>}
            {generatedCode && (
                <Alert severity="success">
                    Join code generated: <strong>{generatedCode}</strong>
                </Alert>
            )}

            <Divider />
            <Button
                variant="outlined"
                fullWidth
                onClick={() => setDeviceControlOpen(true)}
                sx={{ textTransform: "none", borderRadius: 2 }}
            >
                Open Device Controls
            </Button>
            <Dialog
                open={deviceControlOpen}
                onClose={() => setDeviceControlOpen(false)}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle>
                    Device Controls
                    <IconButton
                        onClick={() => setDeviceControlOpen(false)}
                        sx={{ position: "absolute", right: 8, top: 8 }}
                    >
                        <Close />
                    </IconButton>
                </DialogTitle>

                <DialogContent dividers>
                    {/* Lamp selector for device controls */}
                    <Autocomplete<LampDevice>
                        options={lamps ?? []}
                        loading={loading}
                        getOptionLabel={(d) => d?.name ?? ""}
                        value={controlLamp}
                        onChange={(_, v) => setControlLamp(v)}
                        isOptionEqualToValue={(o, v) => o.deviceId === v.deviceId && o.sku === v.sku}
                        renderInput={(params) => (
                            <TextField
                                {...params}
                                label="Select Lamp"
                                placeholder="Pick a lamp to control"
                                helperText={
                                    controlLamp
                                        ? `SKU: ${controlLamp.sku} • ID: ${controlLamp.deviceId}`
                                        : "Choose a lamp to adjust lighting"
                                }
                                InputProps={{
                                    ...params.InputProps,
                                    endAdornment: (
                                        <>
                                            {loading ? <CircularProgress size={18} sx={{ mr: 1 }} /> : null}
                                            {params.InputProps.endAdornment}
                                        </>
                                    ),
                                }}
                                fullWidth
                            />
                        )}
                    />

                    <Divider sx={{ my: 2 }} />

                    <Stack spacing={3} sx={{ mt: 1 }}>
                        {/* Music Mode */}
                        <FormControl fullWidth>
                            <InputLabel id="music-mode-label">Music Mode</InputLabel>
                            <Select
                                labelId="music-mode-label"
                                label="Music Mode"
                                value={musicMode}
                                onChange={(e) => setMusicMode(e.target.value as number | "")}
                                disabled={!controlLamp}
                            >
                                {MUSIC_MODE_OPTIONS.map((m) => (
                                    <MenuItem key={m.value} value={m.value}>
                                        {m.label}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        <Button
                            variant="contained"
                            onClick={async () => {
                                if (!controlLamp || musicMode === "") return;
                                await puzzleControlService.post(
                                    controlLamp.sku,
                                    controlLamp.deviceId,
                                    ["musicMode", { musicMode: Number(musicMode), sensitivity: 100, autoColor: 1 }]
                                );
                            }}
                            disabled={!controlLamp || musicMode === ""}
                        >
                            Apply Music Mode
                        </Button>

                        <Divider />

                        {/* Dynamic Scene */}
                        <FormControl fullWidth>
                            <InputLabel id="scene-label">Dynamic Scene</InputLabel>
                            <Select
                                labelId="scene-label"
                                label="Dynamic Scene"
                                value={selectedScene ? selectedScene.id : ""}
                                onChange={(e) => {
                                    const scene =
                                        DYNAMIC_SCENE_OPTIONS.find((s) => s.id === Number(e.target.value)) || null;
                                    setSelectedScene(scene);
                                }}
                                disabled={!controlLamp}
                            >
                                {DYNAMIC_SCENE_OPTIONS.map((scene) => (
                                    <MenuItem key={scene.id} value={scene.id}>
                                        {scene.label}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        <Button
                            variant="contained"
                            onClick={async () => {
                                if (!controlLamp || !selectedScene) return;
                                await puzzleControlService.post(
                                    controlLamp.sku,
                                    controlLamp.deviceId,
                                    ["lightScene", selectedScene.id]
                                );
                            }}
                            disabled={!controlLamp || !selectedScene}
                        >
                            Apply Scene
                        </Button>

                        <Divider />

                        {/* Brightness */}
                        <Typography variant="subtitle1">Brightness</Typography>
                        <Stack direction="row" spacing={2} alignItems="center">
                            <Slider
                                value={brightness}
                                onChange={(_, v) => setBrightness(v as number)}
                                valueLabelDisplay="auto"
                                min={1}
                                max={100}
                                disabled={!controlLamp}
                            />
                            <Button
                                variant="contained"
                                onClick={async () => {
                                    if (!controlLamp) return;
                                    await puzzleControlService.post(
                                        controlLamp.sku,
                                        controlLamp.deviceId,
                                        ["brightness", Math.max(1, Math.min(100, Number(brightness)))]
                                    );
                                }}
                                disabled={!controlLamp}
                            >
                                Apply
                            </Button>
                        </Stack>

                        <Divider />

                        {/* Reset Lamp */}
                        <Button
                            variant="outlined"
                            color="error"
                            onClick={async () => {
                                if (!controlLamp) return;
                                await puzzleControlService.post(
                                    controlLamp.sku,
                                    controlLamp.deviceId,
                                    ["switchColor", [0, 0, 0]]
                                );
                            }}
                            disabled={!controlLamp}
                            sx={{
                                alignSelf: "flex-end",
                                mt: 1,
                                borderRadius: 2,
                                textTransform: "none",
                            }}
                        >
                            Reset Lamp
                        </Button>
                    </Stack>
                </DialogContent>

                <DialogActions>
                    <Button onClick={() => setDeviceControlOpen(false)}>Close</Button>
                </DialogActions>
            </Dialog>
        </Stack>
    );
}