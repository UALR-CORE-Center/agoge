import Cancel from "@mui/icons-material/Cancel";
import PersonAddIcon from "@mui/icons-material/PersonAdd";
import {LoadingButton} from "@mui/lab";
import {
    Box,
    Button,
    Checkbox,
    Dialog,
    DialogContent,
    DialogTitle,
    Divider,
    FormControlLabel,
    FormGroup,
    FormHelperText,
    TextField
} from "@mui/material";
import DialogActions from "@mui/material/DialogActions";
import {useModal} from "mui-modal-provider";
import React, {useState} from "react";
import {AgogeUser} from "../../../services/User/user.model";
import {userService} from "../../../services/User/user.service";
import SimpleSnackbar from "../../Common/SnackBar/SnackBar";


interface DialogProps {
    open: boolean;
    handleClose: () => void;
    updateUserList: (p: (AgogeUser)) => void;
}

export const CreateUserDialog: React.FC<DialogProps> = (props) => {
    const {showModal} = useModal();

    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [newUserEmail, setNewUserEmail] = useState<string>('');
    const [newUserPermissions, setNewUserPermissions] = useState<{ [key: string]: boolean }>({
        admin: false,
        instructor: false,
        student: false,
    });

    const handleClose = ()  => {
        if (props.handleClose) {
            setNewUserEmail('');
            setNewUserPermissions({
                admin: false,
                instructor: false,
                student: false,
            });
            props.handleClose();
        }
    }

    const handleSnackbar = (message: string, severity: "success" | "error") => {
        showModal(SimpleSnackbar, {
            message: message,
            severity: severity
        });
    }

    const handleCreateUser = async () => {
        setIsLoading(true);

        const newUser = {
            email: newUserEmail,
            permissions: newUserPermissions,
        };

        try {
            const response = await userService.create(newUser);
            props.updateUserList(response);
            handleSnackbar("Successfully created user!", "success");
        } catch (error) {
            console.error(error);
            handleSnackbar("Failed to create user!", "error");
        } finally {
            setIsLoading(false);
            handleClose();
        }
    };

    const handleNewUserCheckboxChange = (role: string) => {
        setNewUserPermissions(prevPermissions => ({
            ...prevPermissions,
            [role]: !prevPermissions[role]
        }));
    };

    const getRoleHelperText = (role: string) => {
        if (role === 'admin') {
            return "Can access any page in Agoge. " +
                "Has permissions to manage instructions, labs, lab specs, servers, and users.";
        } else if (role === 'instructor') {
            return "Can access all instructor and student pages. " +
                "Has permissions to create labs, lab specs, and servers. " +
                "Cannot delete servers, lab specs, or instructions. ";
        } else {
            return "Can be considered public access. Can only access designated student endpoints. " +
                "Does not have permissions to create or destroy any resource.";
        }
    }

    return (
        <>
            <Dialog
                open={props.open}
                onClose={handleClose}
                aria-labelledby="create-user-dialog-title"
                aria-describedby="create-user-dialog-description"
            >
                <DialogTitle id={"create-user-dialog-title"}>Create User</DialogTitle>
                
                <DialogContent>
                    <TextField
                        label="Email"
                        value={newUserEmail}
                        slotProps={{
                            htmlInput: {
                                inputMode: "email"
                            }
                        }}
                        onChange={(e) => setNewUserEmail(e.target.value)}
                        variant="outlined"
                        fullWidth
                        margin="normal"
                        autoComplete={"email"}
                    />
                    <Box p={1}>
                        {Object.keys(newUserPermissions).map(role => (
                            <React.Fragment key={role}>
                                <FormGroup>
                                    <FormControlLabel
                                        control={
                                            <Checkbox
                                                checked={newUserPermissions[role]}
                                                onChange={() => handleNewUserCheckboxChange(role)}
                                            />
                                        }
                                        label={role.charAt(0).toUpperCase() + role.slice(1)}
                                    />
                                    <FormHelperText>{getRoleHelperText(role)}</FormHelperText>
                                </FormGroup>
                                <Divider sx={{my: 1}} />
                            </React.Fragment>
                        ))}
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Box
                        sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            mt: 2
                        }}
                    >
                        <Button
                            onClick={handleClose}
                            variant="contained"
                            startIcon={<Cancel />}
                            color="error"
                            sx={{mr:2}}
                        >
                            Cancel
                        </Button>
                        <LoadingButton
                            onClick={handleCreateUser}
                            variant="contained"
                            color="primary"
                            startIcon={<PersonAddIcon />}
                            loading={isLoading}
                            loadingPosition="start"
                        >
                            Create User
                        </LoadingButton>
                    </Box>
                </DialogActions>
            </Dialog>
        </>
    );
}