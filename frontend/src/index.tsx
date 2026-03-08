import { LicenseInfo } from '@mui/x-license';
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

import './styles/index.css';
import {AuthProvider} from "./provider/AuthProvider";

LicenseInfo.setLicenseKey(import.meta.env.VITE_MUI_LICENSE!);


const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);
root.render(
    <AuthProvider>
        {import.meta.env.VITE_ENV === 'production' ? (
            <App />
        ) : (
            <React.StrictMode>
                <App />
            </React.StrictMode>
        )}
    </AuthProvider>
);
