import React, { createContext, useContext, useState } from 'react';

interface DrawerContextProps {
    isOpen: boolean;
    openDrawer: (data: DrawerData) => void;
    closeDrawer: () => void;
    drawerData: DrawerData;
    showDrawerButton: boolean;
    setShowButton: (value: boolean) => void;
}

interface DrawerData {
    header: string;
    items: {
        title: string;
        text: string;
        icon?: React.ReactNode;
        time?: string;
    }[];
}

export const DrawerContext = createContext<DrawerContextProps | undefined>(undefined);

export const DrawerProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [drawerData, setDrawerData] = useState<DrawerData>({
        header: '',
        items: [],
    });
    const [showDrawerButton, setShowButton] = useState(false);

    const openDrawer = (data: DrawerData) => {
        setDrawerData(data);
        setIsOpen(true);
    };

    const closeDrawer = () => {
        setIsOpen(false);
        setDrawerData({
            header: '',
            items: [],
        });
    };

    return (
        <DrawerContext.Provider value={{ isOpen, openDrawer, closeDrawer, drawerData, showDrawerButton, setShowButton }}>
            {children}
        </DrawerContext.Provider>
    );
};

export const useDrawer = (): DrawerContextProps => {
    const context = useContext(DrawerContext);
    if (!context) {
        throw new Error('useDrawer must be used within a DrawerProvider');
    }
    return context;
};