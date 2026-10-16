import {Typography, Link, Box, Container, styled, useMediaQuery} from "@mui/material";
import {useTheme} from "@mui/material/styles";
import React from 'react';
import { Outlet } from 'react-router-dom';
import {useDrawer} from "./InfoDrawer/InfoDrawerContext";
import AgogeAppBar from './NavigationBar/AgogeAppBar';

interface LayoutProps {
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
            <Link color="inherit" href="https://github.com/UALR-CORE-Center">
                UALR CORE Center
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
            sx={{
                py: 3,
                px: 2,
                mt: 'auto',
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

// Reserves the height of the fixed AppBar so page content starts below it.
const Offset = styled('div')(({ theme }) => theme.mixins.toolbar);

// Keep in sync with the paper width in InfoDrawer.
export const INFO_DRAWER_WIDTH = 'min(25%, 350px)';

const Layout: React.FC<LayoutProps> = ({ onSidebarToggle }) => {
    const { isOpen } = useDrawer();
    const theme = useTheme();
    // Below md the info drawer overlays the page instead of pushing it aside.
    const isDesktop = useMediaQuery(theme.breakpoints.up('md'));

    return (
        <Box
            sx={{
                display: 'flex',
                flexDirection: 'column',
                transition: 'margin-right 0.3s ease',
                minHeight: '100vh',
                // dvh tracks the mobile browser chrome; 100vh above is the fallback.
                '@supports (min-height: 100dvh)': { minHeight: '100dvh' },
                marginRight: isOpen && isDesktop ? INFO_DRAWER_WIDTH : 0,
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
                />
            </Box>

            <Offset />
            <Box
                id="main-content"
                component="main"
                role="main"
                tabIndex={-1}
                sx={{
                    flex: '1 0 auto',
                    width: '100%',
                    // Lets wide children (data grids, code blocks) scroll inside
                    // themselves rather than stretching the page past the viewport.
                    minWidth: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    pt: { xs: 2, md: 3 },
                    px: { xs: 1, sm: 2, md: 3 },
                }}
            >
                <Outlet />
            </Box>
            <Footer />
        </Box>
    );
};

export default Layout;