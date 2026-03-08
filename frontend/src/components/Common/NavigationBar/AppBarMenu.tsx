import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import { Menu, MenuItem, IconButton, ListItemIcon, MenuProps, Typography } from '@mui/material';
import React, { useState, MouseEvent } from 'react';
import { Link } from "react-router-dom";

interface AppBarMenuProps {
    iconText: string;
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
                overflow: textOverflow ? 'hidden' : 'visible',
                textOverflow: textOverflow ? 'ellipsis' : 'clip',
                whiteSpace: textOverflow ? 'nowrap' : 'normal',
                maxWidth: textOverflow ? '150px' : 'none',
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
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    width: width || '200px',
                    borderRadius: '4px',
                    margin: '2px'
                }}
            >
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
                            width: "200px"
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
