import {Paper, Container} from '@mui/material';
import React from 'react';
import '../../../styles/theme'
import {useAuthContext} from "../../../context/AuthContext";
import SettingsBoxes from "./SettingBoxes";

const TeacherSettings: React.FC = () => {
    const { firebaseUser } = useAuthContext();

    return (
        <Container>
            <Paper
                id="settings-page"
                elevation={1}
                sx={{m: 10}}
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