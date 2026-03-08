import { Container, Paper } from "@mui/material";
import React from "react";
import {GlobalImageTable} from "./GlobalImageTable";


export const GlobalImageManager: React.FC = () => {
    return (
        <>
            <Container maxWidth={"lg"}>
                <Paper
                    sx={{
                        mt: 10,
                        height: "auto",
                        display: "flex",
                        flexDirection: "column",
                        overflow: "hidden",
                        padding: 1,
                    }}
                    square={false}
                    >
                        <GlobalImageTable />
                </Paper>
            </Container>
        </>
    )
}