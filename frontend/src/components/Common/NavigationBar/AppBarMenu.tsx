import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import { Box, Menu, MenuItem, IconButton, ListItemIcon, MenuProps, Typography } from '@mui/material';
import React, { useState, MouseEvent } from 'react';
import { Link } from "react-router-dom";

interface AppBarMenuProps {
    iconText: string;
    /** Shown in place of iconText on phone-width screens, where the label doesn't fit. */
    icon?: React.ReactNode;
    textOverflow: boolean;
    menuItems: {
        label: string;
        onClick?: () => void;
        icon?: React.ReactNode;
        to?: string;
    }[];
    edge?: 'start' | 'end' | false;
    color?: 'inherit' | 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning';
    width?: number;
    menuProps?: MenuProps;
}

const AppBarMenu: React.FC<AppBarMenuProps> = (
    {
        iconText,
        icon,
        textOverflow,
        menuItems,
        edge = 'end',
        color = 'inherit',
        width,
        menuProps
    }
) => {
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

    const handleMenuOpen = (event: MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleMenuClose = () => {
        setAnchorEl(null);
    };

    const renderIconText = (iconText: string, textOverflow: boolean) => (
        <Typography
            variant="body1"
            noWrap={textOverflow}
            sx={{
                display: icon ? { xs: 'none', sm: 'block' } : 'block',
                overflow: textOverflow ? 'hidden' : 'visible',
                textOverflow: textOverflow ? 'ellipsis' : 'clip',
                whiteSpace: textOverflow ? 'nowrap' : 'normal',
                maxWidth: textOverflow ? { sm: '120px', md: '150px' } : 'none',
                marginRight: '2px'
            }}
        >
            {iconText}
        </Typography>
    );

    return (
        <>
            <IconButton
                edge={edge}
                color={color}
                onClick={handleMenuOpen}
                aria-label={iconText}
                aria-haspopup="true"
                aria-expanded={Boolean(anchorEl)}
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    width: width ?? 'auto',
                    flexShrink: 0,
                    px: { xs: 0.5, sm: 1 },
                    borderRadius: '4px',
                    margin: '2px'
                }}
            >
                {icon && (
                    <Box component="span" sx={{ display: { xs: 'inline-flex', sm: 'none' } }}>
                        {icon}
                    </Box>
                )}
                {renderIconText(iconText, textOverflow)}
                <ArrowDropDownIcon fontSize="small" />
            </IconButton>
            <Menu
                {...menuProps}
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={handleMenuClose}
                anchorOrigin={{
                    vertical: 'bottom',
                    horizontal: 'right',
                }}
                transformOrigin={{
                    vertical: 'top',
                    horizontal: 'right',
                }}
            >
                {menuItems.map((item, index) => (
                    <MenuItem
                        key={index}
                        onClick={() => {
                            if (item.onClick) item.onClick();
                            handleMenuClose();
                        }}
                        component={item.to ? Link : "div"}
                        to={item.to}
                        sx={{
                            minWidth: "200px"
                        }}
                    >
                        {item.icon && <ListItemIcon>{item.icon}</ListItemIcon>}
                        {item.label}
                    </MenuItem>
                ))}
            </Menu>
        </>
    );
};

export default AppBarMenu;
