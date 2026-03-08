import { TextField } from "@mui/material";
import React, { useState, useEffect } from "react";

interface Props extends React.ComponentProps<typeof TextField> {
    min?: number;
    max?: number;
    onChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
    onBlur?: (event: React.FocusEvent<HTMLInputElement>) => void;
}

const NumberInputField: React.FC<Props> = ({
    min,
    max,
    value,
    helperText,
    onChange,
    onBlur,
    ...props
}) => {
    const [internalValue, setInternalValue] = useState<string>(value as string || "");
    const [error, setError] = useState<boolean>(false);
    const minValue = min || 1;
    const maxValue = max || 250;

    useEffect(() => {
        setInternalValue(value as string || "");
    }, [value]);

    const validateNumber = (inputValue: string) => {
        const input = Number(inputValue);
        if (input < minValue || input > maxValue) {
            setError(true);
        } else {
            setError(false);
        }
    };

    const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
        validateNumber(e.target.value);
        if (onBlur) {
            onBlur(e);
        }
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setInternalValue(e.target.value);
        if (onChange) {
            onChange(e);
        }
    };

    return (
        <TextField
            {...props}
            autoComplete="off"
            type="number"
            variant="outlined"
            onChange={handleChange}
            onBlur={handleBlur}
            error={error}
            value={internalValue}
            slotProps={{
                inputLabel: {
                    shrink: true,
                },
                htmlInput: {
                    min: minValue,
                    max: maxValue,
                }
            }}
            helperText={error ? `Must be a number between ${minValue} and ${maxValue}` : helperText}
        />
    );
}

export default NumberInputField;
