import {Delete as DeleteIcon, Person} from "@mui/icons-material";
import {LoadingButton} from "@mui/lab";
import {
    Box,
    Button,
    Dialog,
    DialogContent,
    DialogTitle,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Typography
} from "@mui/material";
import DialogActions from "@mui/material/DialogActions";
import {useModal} from "mui-modal-provider";
import React, {useState} from "react";
import {AgogeUser} from "../../../services/User/user.model";
import {userService} from "../../../services/User/user.service";
import SimpleSnackbar from "../../Common/SnackBar/SnackBar";


interface DialogProps {
    open: boolean;
    selectedUser: AgogeUser | null;
    handleClose: () => void;
    updateUserList: (user: AgogeUser, filter: boolean) => void;
}

export const DeleteUserDialog: React.FC<DialogProps> = (props) => {
    const {showModal} = useModal();
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const selectedUser = props.selectedUser

    const handleSnackbar = (message: string, severity: "success" | "error") => {
        showModal(SimpleSnackbar, {
            message: message,
            severity: severity
        });
    }

    const handleClose = () => {
        if (props.handleClose) {
            props.handleClose()
        }
    }

    const handleConfirmDelete = async () => {
        if (selectedUser) {
            setIsLoading(true);

            try {
                await userService.delete_user(selectedUser.uid);
                props.updateUserList(selectedUser, true);
                handleSnackbar("Successfully deleted user!", "success");
            } catch (error) {
                handleSnackbar("Failed to delete user!", "error");
            }
            setIsLoading(false);
            handleClose()
        }
    };

    return (
        <>
            <Dialog
                open={props.open}
                onClose={handleClose}
                aria-labelledby="delete-user-dialog-title"
                aria-describedby="delete-user-dialog-description"
            >
                <DialogTitle id={"create-user-dialog-title"}>Confirm Deletion</DialogTitle>
                <DialogContent>
                    <Typography>Are you sure you want to delete this user?</Typography>
                    <List sx={{mt: 1}}>
                        <ListItem>
                            <ListItemIcon>
                                <Person />
                            </ListItemIcon>
                            <ListItemText>
                                <em>{selectedUser?.email}</em>
                            </ListItemText>
                        </ListItem>
                    </List>
                </DialogContent>
                <DialogActions>
                    <Box mt={1}>
                        <Button
                            onClick={handleClose}
                            sx={{ mr: 2}}
                            autoFocus
                            variant={"outlined"}
                            color={"inherit"}
                        >
                            Cancel
                        </Button>
                        <LoadingButton
                            onClick={handleConfirmDelete}
                            variant={"contained"}
                            color="secondary"
                            startIcon={<DeleteIcon />}
                            loading={isLoading}
                            loadingPosition="start"
                        >
                            Confirm Delete
                        </LoadingButton>
                    </Box>
                </DialogActions>
            </Dialog>
        </>
    )
}