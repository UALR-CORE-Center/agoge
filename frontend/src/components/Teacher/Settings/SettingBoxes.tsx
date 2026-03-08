import {Save} from "@mui/icons-material";
import {LoadingButton} from "@mui/lab";
import {Box, TextField, FormControl, Skeleton} from '@mui/material';
import Typography from "@mui/material/Typography";
import {useModal} from "mui-modal-provider";
import React, { useEffect, useState } from 'react';
import { useAuthContext } from '../../../context/AuthContext';
import {AgogeUser} from "../../../services/User/user.model";
import {userService} from "../../../services/User/user.service";
import SimpleSnackbar from "../../Common/SnackBar/SnackBar";

// TODO: This could be reworked. Current implementation works, but could be problematic for future updates
const SettingsBoxesV2: React.FC = () => {
    const {agogeUser} = useAuthContext();
    const {showModal} = useModal();
    const [settingsData, setSettingsData] = useState<AgogeUser>();
    const [apiInput, setApiInput] = useState("");
    const [urlInput, setUrlInput] = useState("");
    const [loading, setLoading] = useState<boolean>(true);
    const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
    const userId = agogeUser?.user ? agogeUser.user.uid : "";

    useEffect(() => {
        const fetchSettings = async () => {
            try{
                setLoading(true);
                const fetchedAgogeUser = await userService.get(userId);
                setSettingsData(fetchedAgogeUser);

                //Loading these into variables to load onto the page at the start
                setApiInput(fetchedAgogeUser?.settings.canvas.api ? (fetchedAgogeUser?.settings.canvas.api) : ("") );
                setUrlInput(fetchedAgogeUser?.settings.canvas.url ? (fetchedAgogeUser?.settings.canvas.url) : (""));
            } catch (error) {
                console.error("Failed to fetch user data.", error);
            } finally {
                setLoading(false);
            }
        };
        fetchSettings();
    }, [userId]);

    const [formData, setFormData] = useState({
        uid: userId,
        email: (settingsData?.email ? (settingsData?.email) : ("") ),
        name: (settingsData?.name ? (settingsData?.name) : ("") ),
        permissions: {
            pending: (settingsData?.permissions? (settingsData?.permissions.pending) : false ),
            admin: (settingsData?.permissions? (settingsData?.permissions.admin) : true ),
            instructor: (settingsData?.permissions? (settingsData?.permissions.instructor) : true ),
            student: (settingsData?.permissions? (settingsData?.permissions.student) : true )
        },
        settings: {
            canvas: {
                api: (settingsData?.settings.canvas.api ? (settingsData?.settings.canvas.api) : ("") ),
                url: (settingsData?.settings.canvas.api ? (settingsData?.settings.canvas.url) : ("")),
                secret: (settingsData?.settings.canvas.secret ? (settingsData?.settings.canvas.secret) : (""))
            }
        }
    })

    const handleAPIChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setApiInput(e.target.value)
        const { name, value } = e.target;
        setFormData(prevState => ({
            ...prevState,
            settings: {
                ...prevState.settings,
                canvas: {
                    ...prevState.settings.canvas,
                    [name]: value
                }
            }
        }));
    };

    const handleURLChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setUrlInput(e.target.value)
        const { name, value } = e.target;
        setFormData(prevState => ({
            ...prevState,
            settings: {
                ...prevState.settings,
                canvas: {
                    ...prevState.settings.canvas,
                    [name]: value
                }
            }
        }));

    };


    const handleSubmit = async (e:React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setIsSubmitting(true);
        try {
            await userService.update_settings(userId, formData);
            showModal(SimpleSnackbar, {
                message: "Successfully updated settings!",
                severity: "success"
            });

        } catch (error){
            showModal(SimpleSnackbar, {
                message: "Failed to update settings.",
                severity: "error"
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <Box
            component="form"
            noValidate
            autoComplete="off"
            onSubmit={handleSubmit}
        >
            <Typography
                variant={"h5"}
                component={"h2"}
                paddingBottom={2}
            >
                LMS Configuration
            </Typography>
            <Box id="canvas">
                <FormControl sx={{marginY: 1}} fullWidth>
                    <label>API Key (Canvas)</label>
                    {loading ? (
                        <Skeleton variant="rounded" height={56} />
                    ) : (
                        <TextField
                            name="api"
                            value={apiInput}
                            onChange={handleAPIChange}
                            variant="outlined"
                            required
                            placeholder={"40932~kzUMvWWBhHcfEFDE34RfcSyYDF5HIpnaPId8jeejadf...."}
                            helperText={"Canvas API key"}
                        />
                    )}
                </FormControl>
                <FormControl sx={{marginY: 1}} fullWidth>
                    <label>URL (Canvas)</label>
                    {loading ? (
                        <Skeleton variant="rounded" height={56} />
                    ) : (
                        <TextField
                            name="url"
                            value={urlInput}
                            onChange={handleURLChange}
                            variant="outlined"
                            required
                            placeholder="https://example.com"
                            helperText={"Canvas URL. i.e. https://example.instructure.com/"}
                        />
                    )}
                </FormControl>
            </Box>
            <Box id="save button">
                <LoadingButton
                    type="submit"
                    variant="contained"
                    color="primary"
                    loadingPosition={"start"}
                    loading={isSubmitting}
                    startIcon={<Save />}
                    aria-hidden={"true"}
                >
                    Submit
                </LoadingButton>
            </Box>
        </Box>
    );
};

export default SettingsBoxesV2;