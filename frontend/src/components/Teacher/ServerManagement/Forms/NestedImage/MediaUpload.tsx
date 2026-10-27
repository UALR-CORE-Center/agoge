import {CloudUpload} from "@mui/icons-material";
import {
    Alert,
    Box,
    Button,
    FormControl,
    FormHelperText,
    InputLabel,
    LinearProgress,
    MenuItem,
    Select,
    Stack,
    Typography,
} from "@mui/material";
import React, {useEffect, useRef, useState} from "react";
import {NestedMedia, NestedOsCatalogEntry} from "../../../../../services/Server/nested.model";
import {nestedService} from "../../../../../services/Server/nested.service";
import {usableMedia, validateMediaFile} from "./guestRules";

interface MediaUploadProps {
    // Used for ids and labels; one MediaUpload per guest.
    guestName: string;
    entry: NestedOsCatalogEntry;
    mediaId: string | null;
    media: NestedMedia[];
    error?: string;
    disabled?: boolean;
    onSelect: (mediaId: string | null) => void;
    onUploaded: (media: NestedMedia) => void;
}

interface UploadProgress {
    filename: string;
    loaded: number;
    total: number;
}

export const formatBytes = (bytes: number): string => {
    const units = ["B", "KB", "MB", "GB"];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
        value /= 1024;
        unit++;
    }
    return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
};

// Pick completed media from the library, or upload a file straight to Cloud Storage through the signed URL.
const MediaUpload: React.FC<MediaUploadProps> = (
    {guestName, entry, mediaId, media, error, disabled, onSelect, onUploaded}
) => {
    const [progress, setProgress] = useState<UploadProgress | null>(null);
    const [uploadError, setUploadError] = useState("");
    const controller = useRef<AbortController | null>(null);
    const fileInput = useRef<HTMLInputElement>(null);
    // An upload runs for minutes; calling the onUploaded from when it started would write back the guest list
    // as it was then, discarding every edit made meanwhile.
    const latestOnUploaded = useRef(onUploaded);
    latestOnUploaded.current = onUploaded;

    // Leaving the step abandons an upload in flight: its progress lives here, and the service deletes the
    // unfinished record when the request is aborted.
    useEffect(() => () => controller.current?.abort(), []);

    const options = usableMedia(media, entry);
    const selectId = `nested-guest-${guestName}-media`;

    const upload = async (file: File) => {
        const problem = validateMediaFile(file, entry);
        if (problem) {
            setUploadError(problem);
            return;
        }
        setUploadError("");
        controller.current = new AbortController();
        setProgress({filename: file.name, loaded: 0, total: file.size});
        try {
            const uploaded = await nestedService.upload_media(file, {
                osId: entry.id,
                signal: controller.current.signal,
                onProgress: (loaded, total) => setProgress({filename: file.name, loaded, total}),
            });
            latestOnUploaded.current(uploaded);
        } catch (e) {
            if (!controller.current?.signal.aborted) {
                setUploadError(`Upload failed: ${(e as Error)?.message || "unknown error"}`);
            }
        } finally {
            controller.current = null;
            setProgress(null);
        }
    };

    const percent = progress && progress.total > 0 ? Math.round(progress.loaded / progress.total * 100) : 0;

    return (
        <Stack gap={1}>
            <Typography variant="subtitle2" component="h4">Installation media</Typography>
            <Typography variant="body2" color="text.secondary">
                {`${entry.display_name} needs media you provide (${entry.media_formats.join(", ")}).`}
            </Typography>
            <Stack direction={{xs: "column", sm: "row"}} gap={2} alignItems={{sm: "flex-start"}}>
                <FormControl fullWidth error={!!error} disabled={disabled || !!progress}>
                    <InputLabel id={`${selectId}-label`}>Media</InputLabel>
                    <Select
                        labelId={`${selectId}-label`}
                        label="Media"
                        value={options.some(item => item.id === mediaId) ? mediaId : ""}
                        onChange={(event) => onSelect(event.target.value || null)}
                    >
                        <MenuItem value=""><em>None</em></MenuItem>
                        {options.map(item => (
                            <MenuItem key={item.id} value={item.id}>
                                {`${item.filename} (${formatBytes(item.size_bytes)})`}
                            </MenuItem>
                        ))}
                    </Select>
                    <FormHelperText>{error || "Completed uploads that fit this OS."}</FormHelperText>
                </FormControl>
                <Box sx={{flexShrink: 0, mt: {sm: 1}}}>
                    <input
                        ref={fileInput}
                        type="file"
                        hidden
                        data-testid={`${selectId}-file`}
                        accept={entry.media_formats.map(format => `.${format}`).join(",")}
                        onChange={(event) => {
                            const file = event.target.files?.[0];
                            event.target.value = "";
                            if (file) {
                                void upload(file);
                            }
                        }}
                    />
                    <Button
                        variant="outlined"
                        startIcon={<CloudUpload />}
                        disabled={disabled || !!progress}
                        onClick={() => fileInput.current?.click()}
                    >
                        Upload
                    </Button>
                </Box>
            </Stack>
            {progress && (
                <Stack gap={0.5} aria-label={`Uploading ${progress.filename}`}>
                    <Stack direction="row" justifyContent="space-between" alignItems="center" gap={1}>
                        <Typography variant="body2" noWrap>
                            {`${progress.filename}: ${formatBytes(progress.loaded)} of ${formatBytes(progress.total)}`}
                        </Typography>
                        <Button size="small" color="error" onClick={() => controller.current?.abort()}>
                            Cancel upload
                        </Button>
                    </Stack>
                    <LinearProgress variant="determinate" value={percent} aria-label="Upload progress" />
                </Stack>
            )}
            {uploadError && <Alert severity="error">{uploadError}</Alert>}
        </Stack>
    );
};

export default MediaUpload;
