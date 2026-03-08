import { useState } from "react";

export const useLocalStorage = () => {
    const [value, setValue] = useState<string | null>(null);

    const setItem = (key: string, newValue: string) => {
        localStorage.setItem(key, newValue);
        setValue(newValue);
    };

    const getItem = (key: string) => {
        const stored = localStorage.getItem(key);
        setValue(stored);
        return value;
    };

    const removeItem = (key: string) => {
        localStorage.removeItem(key);
        setValue(null);
    };

    return { value, setItem, getItem, removeItem };
};