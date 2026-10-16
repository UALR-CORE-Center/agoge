import {Paper, Container} from '@mui/material';
import React from 'react';
import '../../../styles/theme'
import {useAuthContext} from "../../../context/AuthContext";
import SettingsBoxes from "./SettingBoxes";

const TeacherSettings: React.FC = () => {
    const { firebaseUser } = useAuthContext();

    return (
        <Container disableGutters sx={{width: '100%'}}>
            <Paper
                id="settings-page"
                elevation={1}
                sx={{my: {xs: 0, md: 4}, mx: {xs: 0, md: 10}}}
                style={{
                    padding: "15px",
                }}
            >
                <SettingsBoxes />
            </Paper>
        </Container>
    );
};

export default TeacherSettings;