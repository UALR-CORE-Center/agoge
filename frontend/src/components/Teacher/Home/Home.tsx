import { Box } from '@mui/material';
import React from 'react';
import '../../../styles/theme';
import ActiveExpiredUnitTable from "../Home/ActiveExpiredUnitTable";

const TeacherHome: React.FC = () => {
    return (
        <Box id="homePage" sx={{width: '100%', minWidth: 0}}>
            <ActiveExpiredUnitTable />
        </Box>
    );
};

export default TeacherHome;
