import {Search} from "@mui/icons-material";
import {
    Alert,
    Button,
    Chip,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    InputAdornment,
    List,
    ListItemButton,
    ListItemText,
    ListSubheader,
    Stack,
    TextField,
    Typography,
} from "@mui/material";
import React, {useMemo, useState} from "react";
import {NestedOsCatalogEntry, NestedOsGroup} from "../../../../../services/Server/nested.model";
import {osChipLabels} from "./guestRules";

const GROUP_LABELS: Record<NestedOsGroup, string> = {
    kali: "Kali",
    linux: "Linux",
    windows_client: "Windows client",
    windows_server: "Windows Server",
    appliance: "Appliances",
};
const GROUP_ORDER: NestedOsGroup[] = ["kali", "linux", "windows_server", "windows_client", "appliance"];

export const OsChips: React.FC<{entry: NestedOsCatalogEntry}> = ({entry}) => (
    <Stack direction="row" gap={0.5} flexWrap="wrap" component="span">
        {osChipLabels(entry).map(label => (
            <Chip
                key={label}
                size="small"
                label={label}
                variant="outlined"
                color={label === "Upload required" || label === "Manual install" ? "warning" : "default"}
            />
        ))}
    </Stack>
);

interface OsPickerDialogProps {
    open: boolean;
    catalog: NestedOsCatalogEntry[];
    pending?: boolean;
    error?: string;
    onClose: () => void;
    onConfirm: (entry: NestedOsCatalogEntry) => void;
}

const matches = (entry: NestedOsCatalogEntry, query: string): boolean => {
    const needle = query.trim().toLowerCase();
    return !needle || [entry.display_name, entry.version, entry.id, GROUP_LABELS[entry.group] ?? ""]
        .some(text => text.toLowerCase().includes(needle));
};

// Grouped by catalog group, searchable; the license note is shown before the choice is confirmed.
const OsPickerDialog: React.FC<OsPickerDialogProps> = ({open, catalog, pending, error, onClose, onConfirm}) => {
    const [query, setQuery] = useState("");
    const [selectedId, setSelectedId] = useState<string | null>(null);

    const groups = useMemo(() => GROUP_ORDER
        .map(group => ({
            group,
            entries: catalog.filter(entry => entry.is_enabled && entry.group === group && matches(entry, query)),
        }))
        .filter(({entries}) => entries.length > 0), [catalog, query]);
    const selected = catalog.find(entry => entry.id === selectedId) ?? null;

    const close = () => {
        setQuery("");
        setSelectedId(null);
        onClose();
    };
    const confirm = () => {
        if (selected) {
            onConfirm(selected);
            close();
        }
    };

    return (
        <Dialog open={open} onClose={close} fullWidth maxWidth="sm" aria-labelledby="nested-os-picker-title">
            <DialogTitle id="nested-os-picker-title">Choose an operating system</DialogTitle>
            <DialogContent dividers>
                <Stack gap={2}>
                    {error && <Alert severity="error">{error}</Alert>}
                    <TextField
                        size="small"
                        label="Search"
                        autoComplete="off"
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                        slotProps={{input: {startAdornment: <InputAdornment position="start"><Search /></InputAdornment>}}}
                    />
                    {pending && <Typography color="text.secondary">Loading the catalog…</Typography>}
                    {!pending && groups.length === 0 && (
                        <Typography color="text.secondary">No operating system matches.</Typography>
                    )}
                    <List dense aria-label="Operating systems" sx={{maxHeight: 360, overflowY: "auto"}}>
                        {groups.map(({group, entries}) => (
                            <li key={group}>
                                <ul style={{padding: 0}}>
                                    <ListSubheader>{GROUP_LABELS[group]}</ListSubheader>
                                    {entries.map(entry => (
                                        <ListItemButton
                                            key={entry.id}
                                            selected={entry.id === selectedId}
                                            onClick={() => setSelectedId(entry.id)}
                                        >
                                            <ListItemText
                                                primary={entry.display_name}
                                                secondary={<OsChips entry={entry} />}
                                                slotProps={{secondary: {component: "span"}}}
                                            />
                                        </ListItemButton>
                                    ))}
                                </ul>
                            </li>
                        ))}
                    </List>
                    {selected && (
                        <Alert severity="info" aria-label="License note">
                            <Typography variant="subtitle2" component="p">{selected.display_name}</Typography>
                            {selected.license_note || "No license note."}
                        </Alert>
                    )}
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={close}>Cancel</Button>
                <Button variant="contained" disabled={!selected} onClick={confirm}>Add guest</Button>
            </DialogActions>
        </Dialog>
    );
};

export default OsPickerDialog;
