import {DangerousOutlined, PlayArrowOutlined} from "@mui/icons-material";
import Cancel from "@mui/icons-material/Cancel";
import ComputerIcon from "@mui/icons-material/Computer";
import DeleteForeverOutlinedIcon from "@mui/icons-material/DeleteForeverOutlined";
import LockOpenOutlinedIcon from "@mui/icons-material/LockOpenOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import {Backdrop, Box, Skeleton} from "@mui/material";
import React, {useEffect} from "react";
import {useAuthContext} from "../../../context/AuthContext";
import {useDrawer} from "../../Common/InfoDrawer/InfoDrawerContext";
import ImageListTable from "./ImageListTable";

const ServerManager: React.FC = () => {
    const {firebaseUser } = useAuthContext();
    const { setShowButton, drawerData } = useDrawer();

    useEffect(() => {
        setShowButton(true);
        drawerData.header = "Server Manager Information";
        drawerData.items = [
            { title: "Create Image", text: "Create a new server to use and customize for labs.", icon: <ComputerIcon fontSize={"medium"}/>, time:"2 mins"},
            { title: "Check in", text: "Save and update changes made to selected server.", icon:<LockOpenOutlinedIcon fontSize={"medium"}/>, time:"5 mins"},
            { title: "Check out", text: "Reserve and make changes to selected server.", icon:<LockOutlinedIcon fontSize={"medium"}/>, time:"2 mins"},
            { title: "Start", text: "Start up the server.", icon:<PlayArrowOutlined fontSize={"medium"}/>, time:"2 min"},
            { title: "Stop", text: "Stop the server.", icon:<DangerousOutlined fontSize={"medium"}/>, time:"2 min"},
            { title: "Cancel", text: "Cancel any changes made to selected server.", icon:<Cancel fontSize={"medium"}/>, time:"2 min"},
            { title: "Delete", text: "Delete server from the app.", icon: <DeleteForeverOutlinedIcon fontSize={"medium"}/>, time:"2 min"},
        ];
        return () => {
            setShowButton(false);
        };
    }, [setShowButton, drawerData]);

    return (
        <>
            <Box
                width={"80%"}
                height={"auto"}
                sx={{marginTop: "100px"}}
            >
                { firebaseUser.user ? (
                    <ImageListTable />
                ) : (
                    <Backdrop
                        sx={{
                            color: '#fff',
                            zIndex: (theme) => theme.zIndex.drawer + 1
                        }}
                        open={true}
                    >
                        <Skeleton variant="rectangular" width="100%" height={50} />
                    </Backdrop>
                )}
            </Box>
        </>
    );
};

export default ServerManager;