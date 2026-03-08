import {Container, Paper, Box, Typography, Skeleton, Divider} from "@mui/material";
import React, {useEffect, useState} from "react";
import {useAuthContext} from "../../../context/AuthContext";
import {adminService} from "../../../services/Admin/admin.service";
import {ProjectSettingsModel} from "../../../services/Admin/projectSettings.model";
import {SettingsField} from "./SettingsField";


export const ProjectSettings: React.FC = () => {
    const { agogeUser, firebaseUser } = useAuthContext();
    const [formData, setFormData] = useState<ProjectSettingsModel | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);


    const fetchProjectSettings = async () => {
        setIsLoading(true);
        await adminService.get_project_settings()
        .then((resp) => {
            setFormData((prevState) => ({...prevState, ...resp}));
        }).catch((err) => {
            console.log(err.message);
        }).finally(() => setIsLoading(false));
    }

    useEffect(() => {}, [firebaseUser, agogeUser]);

    useEffect(() => {
        fetchProjectSettings();
    }, []);

    const handleFieldChange = (fieldName: string, newValue: any) => {
        if (!formData) return;
        setFormData((prev) => {
            if (!prev) return null;
            return { ...prev, [fieldName]: newValue };
        });
    };

    const getInputType = (key: string): string => {
        if (key === 'max_workspaces') {
            return "number";
        } else if (key === 'student_workout_firewall') {
            return "boolean";
        } else {
            return "string";
        }
    }

    return (
        <>
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
                    <Box sx={{ height: "auto", width: "100%" }}>
                        <Box sx={{ width: 'auto', m: 5 }}>
                            <Typography variant={"h4"} component={"h2"}>Project Settings</Typography>

                            {   formData ?
                                Object.entries(formData).map(([key, value]) => (
                                    <React.Fragment key={key}>
                                        <Divider variant={"middle"} sx={{m: 1}}/>
                                        <SettingsField
                                            name={key}
                                            value={value}
                                            loading={isLoading}
                                            onChange={handleFieldChange}
                                            inputType={getInputType(key)}
                                        />
                                    </React.Fragment>
                                ))
                                : <Skeleton height={150} variant={"rounded"} animation={"wave"} sx={{mt: 5}}/>
                            }
                            <Divider variant={"middle"} sx={{m: 1}}/>
                        </Box>
                    </Box>
                </Paper>
            </Container>
        </>
    )
}