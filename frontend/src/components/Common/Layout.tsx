import {Typography, Link, Box, Container, styled, Grid2} from "@mui/material";
import React from 'react';
import { Outlet } from 'react-router-dom';
import {useDrawer} from "./InfoDrawer/InfoDrawerContext";
import AgogeAppBar from './NavigationBar/AgogeAppBar';

interface LayoutProps {
    toggleTheme: (event: React.ChangeEvent<HTMLInputElement>, checked: boolean) => void;
    isDarkMode: boolean;
    onSidebarToggle: () => void;
}

interface FooterProps {
    backgroundColor?: string;
}

const Copyright = () => {
    return (
        <Typography variant="body2" color="text.secondary" align="center">
            {'Copyright © '}
            {new Date().getFullYear()}
            {' '}
            <Link color="inherit" href="https://www.bastazo.com/">
                Bastazo, Inc.
            </Link>{' '}
        </Typography>
    );
}

const Footer = ({ backgroundColor = 'background.paper' }: FooterProps) => {
    return (
        <Box
            id={"agoge-footer"}
            component="footer"
            role="contentinfo"
            marginTop={10}
            sx={{
                py: 3,
                px: 2,
                mt: 'auto',
                bottom: 0,
                padding: 'fixed',
            }}
        >
            <Container maxWidth="sm">
                <Typography variant="body1" align="center">
                    Agoge
                </Typography>
                <Copyright />
            </Container>
        </Box>
    );
}

const Offset = styled('div')(({ theme }) => theme.mixins.toolbar);

const Layout: React.FC<LayoutProps> = ({ toggleTheme, isDarkMode, onSidebarToggle }) => {
    const { isOpen } = useDrawer();

    return (
        <Box
            sx={{
                display: 'flex',
                flexDirection: 'column',
                transition: 'margin-right 0.3s ease',
                minHeight: '100vh',
                marginRight: isOpen ? 'min(25%, 350px)' : 0,
            }}
        >
            <Link
                href="#main-content"
                underline="none"
                sx={{
                    position: 'absolute',
                    left: -9999,
                    top: 0,
                    zIndex: 2000,
                    p: 1,
                    bgcolor: 'primary.main',
                    color: 'primary.contrastText',
                    borderRadius: 1,
                    '&:focus-visible': {
                        left: 8,
                        top: 8,
                        outline: '2px solid #fff',
                        outlineOffset: 2,
                    },
                }}
            >
                Skip to main content
            </Link>

            <Box component="nav" role="navigation">
                <AgogeAppBar
                    onSidebarToggle={() => {}}
                    toggleTheme={toggleTheme}
                    isDarkMode={isDarkMode}
                />
            </Box>

            <Grid2
                id="main-content"
                component="main"
                role="main"
                container
                justifyContent="center"
                alignItems="center"
                tabIndex={-1}
            >
                <Outlet />
            </Grid2>
            <Footer />
        </Box>
    );
};

export default Layout;