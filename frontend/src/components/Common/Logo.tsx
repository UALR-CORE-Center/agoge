import {Box} from "@mui/material";
import React from 'react';

const CoreWordmark: React.FC = () => (
    <Box
        component="img"
        src={`${import.meta.env.BASE_URL}images/core-wordmark.png`}
        alt="Cyberspace Operations Research and Education (CORE) Center"
        width={1024}
        height={602}
        sx={{ display: 'block', mx: 'auto', width: '100%', maxWidth: 340, height: 'auto' }}
    />
);

const GuacamoleLogo: React.FC = () => {
    return (
        <img
            src={`${import.meta.env.BASE_URL}images/apache_guacamole_logo.png`}
            alt="Apache Guacamole Logo"
            style={{
                width: '100%',
                backgroundColor: "#f5f5f5",
                borderRadius: '6px',
                padding: '4px',
                maxWidth: '50%'
            }}
        />
    );
};

export { CoreWordmark, GuacamoleLogo };

