import ManageAccountsIcon from '@mui/icons-material/ManageAccounts';
import { Container, Paper, Box, Typography } from "@mui/material";
import React, { useEffect } from "react";
import { useAuthContext } from "../../../context/AuthContext";
import AgogeUserTable from "./AgogeUserTable";

const UserManager: React.FC = () => {
    const { agogeUser, firebaseUser } = useAuthContext();

    useEffect(() => {}, [firebaseUser, agogeUser]);

    return (
        <Container>
            <Paper
                sx={{
                    mt: 10,
                    height: "auto",
                    display: "flex",
                    flexDirection: "column",
                    overflow: "hidden"
                }}
                square={false}
            >
                <Box sx={{margin: "10px 10px 0 10px"}}>
                    <Typography
                        variant={"h4"}
                        component={"h2"}
                        sx={{ mb: 1 }}
                    >
                        <ManageAccountsIcon
                            fontSize={"large"}
                            sx={{ mr: 1 }}
                        />
                        User Manager
                    </Typography>
                </Box>
                <Box sx={{ flex: 1 }}>
                    <AgogeUserTable />
                </Box>
            </Paper>
        </Container>
    )
};

export default UserManager;
