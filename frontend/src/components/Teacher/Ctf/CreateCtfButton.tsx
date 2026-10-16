import FlagIcon from "@mui/icons-material/Flag";
import {LoadingButton} from "@mui/lab";
import {Alert, Box} from "@mui/material";
import React, {useState} from "react";
import {useNavigate} from "react-router-dom";
import {useCtfEnabled} from "../../../hooks/useCtfEnabled";
import {URL_TEACHER_CTF_EVENT} from "../../../router/urls";
import {ctfService} from "../../../services/Ctf/ctf.service";

interface CreateCtfButtonProps {
    buildId: string;
    isExpired: boolean;
}

const CreateCtfButton: React.FC<CreateCtfButtonProps> = ({buildId, isExpired}) => {
    const {ctfEnabled} = useCtfEnabled();
    const navigate = useNavigate();
    const [creating, setCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // With the feature off every /ctf/ route but config answers 404 (SC-19), so the button would only fail.
    if (!ctfEnabled) return null;

    const handleCreate = async () => {
        if (creating || isExpired) return;
        setCreating(true);
        setError(null);
        try {
            const created = await ctfService.create({unit_id: buildId});
            navigate(`${URL_TEACHER_CTF_EVENT}/${created.build_id}`);
        } catch (err) {
            // The API's detail names the reason: too many boards, a workout already on an active event, no seed.
            const {status, message} = (err ?? {}) as {status?: number, message?: string};
            setError(`${status || "Unknown Status"}: ${message || "Could not create the CTF event."}`);
            setCreating(false);
        }
    };

    return (
        <Box sx={{padding: 2}}>
            <LoadingButton
                variant="contained"
                color="primary"
                startIcon={<FlagIcon />}
                loading={creating}
                loadingPosition="start"
                disabled={isExpired}
                onClick={handleCreate}
            >
                Create CTF Event
            </LoadingButton>
            {error && (
                <Alert severity="error" sx={{mt: 2}}>{error}</Alert>
            )}
        </Box>
    );
};

export default CreateCtfButton;
