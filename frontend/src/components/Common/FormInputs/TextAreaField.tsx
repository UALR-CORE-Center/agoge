import {FormControl, TextField} from "@mui/material";
import React, {useState, useEffect} from "react";

interface Props {
    id: string;
    name: string;
    label: string;
    defaultValue?: string;
    helperText?: string;
    required?: boolean;
    maxRows?: number;
    maxLength?: number;
    type?: string;
    error?: boolean;
    onInputChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
}

const TextAreaField: React.FC<Props> = (
    {
        id,
        name,
        label,
        defaultValue,
        helperText,
        required,
        maxRows,
        maxLength,
        type,
        error,
        onInputChange,
    }
) => {
    const [inputValue, setInputValue] = useState<string>(defaultValue || "");
    const [inputLength, setInputLength] = useState<number>(0)

    useEffect(() => {
        if (defaultValue) {
            setInputValue(defaultValue);
            setInputLength(defaultValue.length);
        }
    }, [defaultValue]);

    const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const newValue = event.target.value;
        setInputValue(newValue);
        setInputLength(newValue.length);
        if (onInputChange) {
            onInputChange(event);
        }
    }

    const getHelperText = () => {
        if (maxLength && helperText) {
            return `${helperText} ${inputLength}/${maxLength}`;
        } else if (maxLength && !helperText) {
            return `${inputLength}/${maxLength}`;
        }
        return helperText;
    }

    return (
        <FormControl fullWidth required={required}>
            <TextField
                autoComplete="off"
                id={id}
                name={name}
                label={label}
                type={type}
                value={inputValue}
                helperText={getHelperText()}
                minRows={2}
                maxRows={maxRows || 5}
                margin={"normal"}
                multiline={true}
                onChange={handleInputChange}
                slotProps={{
                    htmlInput: {maxLength: maxLength},
                    input: {
                        style: {
                            overflow: "auto"
                        }
                    }
                }}
                error={error}
            />
        </FormControl>
    );
};

export default TextAreaField;
