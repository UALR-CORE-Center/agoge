import {Backdrop, CircularProgress} from "@mui/material";
import React from "react";

export function SpinnerOverlay () {
    return (
        <React.Fragment>
            <Backdrop open sx={{ color: "#fff", zIndex: theme => theme.zIndex.drawer + 1 }}>
                <CircularProgress />
            </Backdrop>
        </React.Fragment>
    )
}