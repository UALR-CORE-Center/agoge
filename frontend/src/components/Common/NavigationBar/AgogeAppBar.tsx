import {
    AdminPanelSettings,
    Lightbulb,
    LoginRounded,
    ManageAccounts,
    Memory,
    Science,
} from "@mui/icons-material";
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import ComputerIcon from '@mui/icons-material/Computer';
import HelpIcon from '@mui/icons-material/Help';
import HomeIcon from '@mui/icons-material/Home';
import Logout from '@mui/icons-material/Logout';
import Settings from '@mui/icons-material/Settings';
import {
    AppBar,
    Toolbar,
    Tooltip,
    Typography,
    IconButton,
    Box,
} from '@mui/material';
import React, { ChangeEvent } from 'react';
import {useNavigate, useLocation, Link} from 'react-router-dom';

import { useAuthContext } from '../../../context/AuthContext';
import {useLocalStorage} from "../../../hooks/useLocalStorage";
import {
    URL_TEACHER_HOME,
    URL_TEACHER_SERVERS,
    URL_TEACHER_SETTINGS,
    URL_TEACHER_SPECIFICATIONS_BASE,
    URL_LOGIN,
    URL_ADMIN_MANAGE_USERS,
    URL_ADMIN_BASE,
    URL_ADMIN_MANAGE_IMAGES, URL_ADMIN_MANAGE_PROJECT
} from "../../../router/urls";
import { AppUiObjectNames, Users } from "../../../types/AppObjectNames";
import { useDrawer } from "../InfoDrawer/InfoDrawerContext";
import AppBarMenu from "./AppBarMenu";

interface AgogeAppBarProps {
    onSidebarToggle: () => void;
    toggleTheme: (event: ChangeEvent<HTMLInputElement>, checked: boolean) => void;
    isDarkMode: boolean;
}

const AgogeAppBar: React.FC<AgogeAppBarProps> = ({ onSidebarToggle, toggleTheme, isDarkMode }) => {
    const { firebaseUser, agogeUser, logout } = useAuthContext();
    const {setItem} = useLocalStorage();
    const navigate = useNavigate();
    const location = useLocation();
    const { showDrawerButton, openDrawer, drawerData, closeDrawer, isOpen } = useDrawer();

    const handleLogin = () => {
        setItem('redirectAfterLogin', location.pathname);
        navigate(URL_LOGIN);
    };

    const handleLogout = async () => {
        try {
            await logout();
        } catch (error) {
            console.error('Failed to log out:', error);
        }
    };

    const handleToggleTheme = () => {
        toggleTheme({} as ChangeEvent<HTMLInputElement>, !isDarkMode);
    };

    const renderTeacherMenus = () => {
        if (firebaseUser.user && agogeUser?.user && agogeUser?.user?.permissions.instructor) {
            return (
                <>
                    <AppBarMenu
                        iconText={`${Users.TEACHER.toString()}s`}
                        textOverflow={false}
                        menuItems={[
                            {
                                label: `Manage ${AppUiObjectNames.UNIT}s`,
                                icon: <HomeIcon fontSize="small" />,
                                to: URL_TEACHER_HOME
                            },
                            {
                                label: `New ${AppUiObjectNames.UNIT.toString()}`,
                                icon: <Science fontSize="small" />,
                                to: URL_TEACHER_SPECIFICATIONS_BASE
                            },
                            {
                                label: 'Manage Servers',
                                icon: <ComputerIcon fontSize="small" />,
                                to: URL_TEACHER_SERVERS
                            }
                        ]}
                        edge="end"
                        color="inherit"
                    />
                    <AppBarMenu
                        iconText={firebaseUser.user?.displayName || firebaseUser.user.email!}
                        textOverflow={true}
                        menuItems={[
                            {
                                label: 'Settings',
                                icon: <Settings fontSize="small" />,
                                to: URL_TEACHER_SETTINGS
                            },
                            {
                                label: 'Logout',
                                onClick: handleLogout,
                                icon: <Logout fontSize="small" />
                            }
                        ]}
                        edge="end"
                        color="inherit"
                    />
                </>
            );
        }
        return null;
    };

    const renderAdminMenus = () => {
        if (firebaseUser.user && agogeUser?.user && agogeUser?.user?.permissions.admin) {
            return (
                <>
                    <AppBarMenu
                        iconText={`${Users.ADMIN.toString()}s`}
                        textOverflow={false}
                        menuItems={[
                            {
                                label: `Build Manager`,
                                icon: <AdminPanelSettings fontSize="small" />,
                                to: URL_ADMIN_BASE
                            },
                            {
                                label: 'User Manager',
                                icon: <ManageAccounts fontSize="small" />,
                                to: URL_ADMIN_MANAGE_USERS
                            },
                            {
                                label: 'Image Manager',
                                icon: <Memory fontSize="small" />,
                                to: URL_ADMIN_MANAGE_IMAGES
                            },
                            {
                                label: 'Project Settings',
                                icon: <Settings fontSize="small" />,
                                to: URL_ADMIN_MANAGE_PROJECT
                            }
                        ]}
                        edge="end"
                        color="inherit"
                    />
                </>
            )
        }
    }

    return (
        <AppBar
            component="nav"
            sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}
        >
            <Toolbar>
                <Typography
                    variant="h6"
                    noWrap
                    component={Link}
                    to={URL_TEACHER_HOME}
                    sx={{
                        mr: 2,
                        display: { xs: 'none', md: 'flex' },
                        fontFamily: 'monospace',
                        fontWeight: 700,
                        letterSpacing: '.3rem',
                        color: 'white',
                        textDecoration: 'none',
                        cursor: 'pointer',
                    }}
                >
                    {AppUiObjectNames.APP_NAME.toUpperCase()}
                </Typography>
                <Box sx={{ flexGrow: 1 }} />
                {firebaseUser ? (
                    <>
                        {renderAdminMenus()}
                        {renderTeacherMenus()}
                    </>
                ) : (
                    <IconButton
                        edge="end"
                        color="inherit"
                        onClick={handleLogin}
                        sx={{
                            display: 'flex',
                            alignItems: 'center',
                            borderRadius: '4px',
                        }}
                    >
                        <LoginRounded fontSize="small" sx={{ mr: 1 }} />
                        <Typography variant="subtitle1" sx={{ mr: 1 }}>Login</Typography>
                    </IconButton>
                )}
                {showDrawerButton && (
                    <Tooltip title="Details & Time for Actions" leaveDelay={200}>
                        <IconButton
                            color="inherit"
                            onClick={() => {
                                if (isOpen) {
                                    closeDrawer();
                                } else {
                                    openDrawer(drawerData);
                                }
                            }}
                            aria-label={isOpen ? "Close action details" : "Open action details"}
                        >
                            <Lightbulb />
                        </IconButton>
                    </Tooltip>
                )}
                <Tooltip title={"Help & Documentation"} leaveDelay={200}>
                    <IconButton
                        onClick={() => window.open('https://docs.bastazo.com/agoge')}
                        color="inherit"
                        aria-label="Open documentation"
                    >
                        <HelpIcon/>
                    </IconButton>
                </Tooltip>
                <Tooltip title={isDarkMode ? "Toggle light mode" : "Toggle dark mode"} leaveDelay={200}>
                    <IconButton
                        onClick={handleToggleTheme}
                        color="inherit"
                        aria-label={isDarkMode ? "Toggle light mode" : "Toggle dark mode"}
                    >
                        {isDarkMode ? <Brightness4Icon /> : <Brightness7Icon />}
                    </IconButton>
                </Tooltip>
            </Toolbar>
        </AppBar>
    );
};

export default AgogeAppBar;
