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
} from "@mui/material";
import { useDrawer } from './InfoDrawerContext';
import {AccessTime, ChevronRight} from "@mui/icons-material";


export const InfoDrawer: React.FC = () => {
    const { isOpen, drawerData, closeDrawer } = useDrawer();

    return (
        <Drawer
            variant="persistent"
            anchor="right"
            open={isOpen}
            onClose={closeDrawer}
            sx={{
                flexShrink: 0,
                '& .MuiDrawer-paper': {
                    width:'25%',
                    maxWidth: '350px',
                    transition: 'width 0.3s ease',
                },
            }}
        >
            <Box sx={{ padding: 2 }}>
                <Toolbar />
                <Box sx={{display:'flex',flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2}}>
                    <Typography variant="h6" gutterBottom>
                        {drawerData.header}
                    </Typography>
                    <IconButton color="inherit" onClick={closeDrawer}> <ChevronRight fontSize="large"/> </IconButton>
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