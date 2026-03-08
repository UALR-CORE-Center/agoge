import {Paper} from "@mui/material";
import React from 'react';

interface LogoProps {
    contained?: boolean;
}

const AgogeLogo: React.FC<LogoProps> = (
    {contained=true}
) => {

    const logo = () => {
        return (
            <img
                src={`${import.meta.env.BASE_URL}images/Agoge-Logo-Color@2x.png`}
                alt="Agoge Logo"
                style={{
                    width: '100%',
                    borderRadius: '6px',
                    padding: '4px'
                }}
            />
        )
    }
    const renderBordered = () => {
        return (
            <Paper
                variant={"elevation"}
            >
                {logo()}
            </Paper>
        )
    }
    return (
        contained ? (
            renderBordered()
        ) : (
            logo()
        )
    );
};

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

export { AgogeLogo, GuacamoleLogo };

