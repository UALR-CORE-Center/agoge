import React from "react";
import { useLocation, useRouteError, useNavigate } from "react-router-dom";
import { Box, Button, Typography } from "@mui/material";
import { KeyboardReturn } from "@mui/icons-material";
import { AgogeLogo } from "../Logo";
import { URL_BASE } from "../../../router/urls";
import HomeIcon from "@mui/icons-material/Home";

interface RouteError {
    status?: number;
    message?: string;
}

const AppError: React.FC = () => {
    const error = useRouteError();
    const location = useLocation();
    const navigate = useNavigate();

    let status = 500;
    let message = "Oops! Something went wrong...";

    if (error instanceof Error) {
        message = error.message;
    } else if (typeof error === "object" && error !== null) {
        const routeError = error as RouteError;
        status = routeError.status || status;
        message = routeError.message || message;

        if (status === 404) {
            message = "Requested page not found!";
        } else if ([401, 403].includes(status)) {
            message = "Not authorized or you do not have the proper permissions";
        } else {
            message = routeError.message || message;
        }
    }

    if (location.state) {
        const routeStateError = location.state as RouteError;
        status = routeStateError.status || status;
        if (status === 404) {
            message = "Requested page not found!";
        } else if ([401, 403].includes(status)) {
            message = "Not authorized or you do not have the proper permissions";
        } else {
            message = routeStateError.message || message;
        }
    }

    return (
        <Box
            id="homePage"
            sx={{
                backgroundColor: '#1c2538',
                height: '100vh',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
            }}
        >
            <Box
                id="main"
                sx={{
                    backgroundColor: '#ffffff',
                    borderRadius: 4,
                    p: 2,
                    boxShadow: 3,
                    maxWidth: 500,
                }}
            >
                <AgogeLogo contained={false} />
                <Typography
                    mt={0}
                    variant={"h6"}
                    textAlign={"center"}
                    color={"error"}
                >
                    {status} Error
                </Typography>
                <Typography
                    id="error-msg"
                    variant={"body1"}
                    textAlign={"center"}
                    color={"black"}
                >
                    {message}
                </Typography>
                <Box
                    display={"flex"}
                    justifyContent={"space-between"}
                    mt={2}
                >
                    <Button
                        onClick={() => navigate(-1)}
                        startIcon={<KeyboardReturn />}
                        variant={"outlined"}
                        sx={{
                            color: "black",
                            borderColor: "black",
                            width: "200px"
                        }}
                    >
                        Go back
                    </Button>
                    <Button
                        onClick={() => navigate(URL_BASE)}
                        startIcon={<HomeIcon />}
                        variant={"contained"}
                        sx={{
                            color: "white",
                            backgroundColor: "#1c2538",
                            width: "200px"
                        }}
                    >
                        Go home
                    </Button>
                </Box>
            </Box>
        </Box>
    );
}

export default AppError;
