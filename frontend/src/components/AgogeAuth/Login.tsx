import { Box } from '@mui/material';
import React from 'react';
import { FirebaseAuthUI } from './Firebase/FirebaseAuthUI';

const Login: React.FC = () => {

    return (
        <Box
            id="homePage"
            sx={{
                backgroundColor: '#1c2538',
                minHeight: '100vh',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                px: 2,
                py: { xs: 2, sm: 4 },
                boxSizing: 'border-box',
            }}
        >
            <FirebaseAuthUI />
        </Box>
    );
};

export default Login;
