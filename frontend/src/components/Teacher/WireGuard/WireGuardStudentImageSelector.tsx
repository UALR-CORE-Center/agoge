import React, {useEffect, useState} from "react";
import {Alert, Button, FormControl, FormHelperText, InputLabel, MenuItem, Select} from "@mui/material";
import {AgogeImage} from "../../../services/Server/image.model";
import {imageService} from "../../../services/Server/image.service";
import {ImageStates} from "../../../types/AgogeStates";

interface Props {
    open: boolean;
    value: string;
    onChange: (image: string) => void;
    onAvailabilityChange: (available: boolean) => void;
}

export const WireGuardStudentImageSelector: React.FC<Props> = ({open, value, onChange, onAvailabilityChange}) => {
    const [images, setImages] = useState<AgogeImage[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [retry, setRetry] = useState(0);
    useEffect(() => {
        if (!open) return;
        let current = true;
        setLoading(true);
        setError(null);
        onAvailabilityChange(false);
        imageService.list().then(items => {
            if (!current) return;
            const available = items.filter(image => {
                // Legacy records may have one connection object instead of a list.
                const connections = [image.human_interaction].flat().filter(Boolean);
                return Number(image.status) === ImageStates.CHECKED_IN
                && !!image.name
                && (image.image_exists !== false || image.is_shared === true)
                && image.architecture?.toUpperCase() !== "ARM64"
                && connections.some(connection => connection.display && connection.username
                    && connection.password && ["ssh", "rdp", "vnc"].includes(connection.protocol?.trim().toLowerCase()));
            });
            setImages(available);
            if (!available.some(image => image.name === value)) {
                // Submit the Agoge record name. Its underlying Compute image can
                // have a different name or a fully qualified shared-image URL.
                onChange(available.find(image => image.name === "image-kali-linux-2023"
                    || image.image === "image-kali-linux-2023")?.name || "");
            }
            onAvailabilityChange(available.length > 0);
        }).catch(err => {
            if (current) setError(err instanceof Error ? err.message : "Could not load student images.");
        }).finally(() => { if (current) setLoading(false); });
        return () => { current = false; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, retry]);
    const selectedImage = images.find(image => image.name === value);
    return <>
        {error && <Alert severity="error" action={<Button color="inherit" onClick={() => setRetry(n => n + 1)}>Retry images</Button>}>
            {error}
        </Alert>}
        {!loading && !error && images.length === 0 && <Alert severity="info">
            Check in an AMD64 student image with an SSH, RDP, or VNC display connection and password in Server Manager before building.
        </Alert>}
        <FormControl fullWidth required margin="normal" disabled={loading || !!error || images.length === 0}>
            <InputLabel id="wireguard-student-image-label">Student workstation image</InputLabel>
            <Select labelId="wireguard-student-image-label" label="Student workstation image" value={selectedImage ? value : ""}
                onChange={event => onChange(event.target.value)}>
                {images.map(image => <MenuItem key={image.name} value={image.name}>{image.name}</MenuItem>)}
            </Select>
            <FormHelperText>{loading ? "Loading student images…"
                : "Each student receives a workstation from this image. The gateway uses the standard Ubuntu image automatically."}</FormHelperText>
        </FormControl>
    </>;
};
