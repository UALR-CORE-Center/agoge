import React from 'react';
import {
    Drawer,
    Box,
    Typography,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Divider,
    IconButton, Paper, Toolbar,
    useMediaQuery,
    useTheme,
} from "@mui/material";
import { useDrawer } from './InfoDrawerContext';
import {AccessTime, ChevronRight} from "@mui/icons-material";


export const InfoDrawer: React.FC = () => {
    const { isOpen, drawerData, closeDrawer } = useDrawer();
    const theme = useTheme();
    // On desktop the drawer sits beside the page (Layout reserves its width);
    // on phones and tablets a quarter of the screen is too narrow to read, so it
    // overlays the page with a backdrop and closes on tap-outside or Escape.
    const isDesktop = useMediaQuery(theme.breakpoints.up('md'));

    return (
        <Drawer
            variant={isDesktop ? "persistent" : "temporary"}
            anchor="right"
            open={isOpen}
            onClose={closeDrawer}
            ModalProps={{ keepMounted: true }}
            sx={{
                flexShrink: 0,
                '& .MuiDrawer-paper': {
                    // Keep the desktop width in sync with INFO_DRAWER_WIDTH in Layout.
                    width: { xs: 'min(85vw, 350px)', md: '25%' },
                    maxWidth: '350px',
                    transition: 'width 0.3s ease',
                },
            }}
        >
            <Box sx={{ padding: 2 }}>
                {/* Clears the AppBar, which only overlaps the persistent drawer */}
                {isDesktop && <Toolbar />}
                <Box sx={{display:'flex',flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2}}>
                    <Typography variant="h6" gutterBottom>
                        {drawerData.header}
                    </Typography>
                    <IconButton color="inherit" onClick={closeDrawer} aria-label="Close action details"> <ChevronRight fontSize="large"/> </IconButton>
                </Box>
                <List>
                    {drawerData.items.map((item, index) => (
                        <Paper key={index}>
                            <ListItem key={index}>
                                {item.icon && <ListItemIcon>{item.icon}</ListItemIcon>}
                                <ListItemText primary={item.title} secondary={item.text} />
                            </ListItem>
                            {item.time && (
                                <Box
                                    sx={{
                                        display: 'flex',
                                        justifyContent: 'flex-end',
                                        alignItems: 'center',
                                        marginBottom: 1,
                                        marginRight: 2,
                                    }}
                                >
                                    <AccessTime fontSize="small" sx={{ marginRight: 1 }} />
                                    <Typography variant="body2" color="textSecondary">
                                        {item.time}
                                    </Typography>
                                </Box>
                            )}
                            <Divider variant="fullWidth" component="li" />
                        </Paper>
                    ))}
                </List>
            </Box>
        </Drawer>
    );
};