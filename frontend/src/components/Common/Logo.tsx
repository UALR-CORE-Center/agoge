import {Box} from "@mui/material";
import React from 'react';
import {AppUiObjectNames} from "../../types/AppObjectNames";

const AgogeBrand: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
    const emblemSize = compact ? { xs: 28, md: 34 } : 56;

    return (
        <Box
            component="span"
            sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: compact ? { xs: 0.5, md: 1 } : 1.5,
                mb: compact ? 0 : 2,
                color: compact ? 'inherit' : '#1c2538',
                fontFamily: 'monospace',
                fontSize: compact ? { xs: '1rem', md: '1.25rem' } : '2rem',
                fontWeight: 700,
                letterSpacing: compact ? { xs: 'normal', md: '.3rem' } : '.1rem',
                lineHeight: 1.2,
                textTransform: 'uppercase',
            }}
        >
            <Box
                component="img"
                src={`${import.meta.env.BASE_URL}images/core-emblem.png`}
                alt="CORE Center"
                width={96}
                height={96}
                sx={{
                    width: emblemSize,
                    height: emblemSize,
                    bgcolor: 'common.white',
                    borderRadius: 1,
                }}
            />
            {AppUiObjectNames.APP_NAME}
        </Box>
    );
};

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

export { AgogeBrand, CoreWordmark, GuacamoleLogo };

