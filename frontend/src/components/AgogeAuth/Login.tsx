import { Box } from '@mui/material';
import React from 'react';
import { FirebaseAuthUI } from './Firebase/FirebaseAuthUI';

const Login: React.FC = () => {

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
            <FirebaseAuthUI />
        </Box>
    );
};

export default Login;
