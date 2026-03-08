import {Box} from "@mui/material";
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthContext } from '../../context/AuthContext';
import {URL_LOGIN} from "../../router/urls";

const Logout: React.FC = () => {
    const { logout } = useAuthContext();
    const navigate = useNavigate();

    useEffect(() => {
        const doLogout = async () => {
            await logout();
            navigate(URL_LOGIN);
        };

        doLogout();
    }, [logout, navigate]);

    return <Box>Logging out...</Box>;
};

export default Logout;
