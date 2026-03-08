// InputTags.tsx
import {Box, Chip, TextField} from "@mui/material";
import {useTheme} from "@mui/material/styles";
import React, { useRef, useState, useEffect } from "react";

/**
 * Defines the shape of props accepted by the InputTags component.
 */
interface Props {
    id: string;
    name: string;
    helperText?: string;
    required: boolean;
    ariaLabel?: string;
    onTagChanges: (services: string[]) => void;
    tagType?: string;
    initialTags: string[];
}

/**
 * InputTags component renders an input field for adding tags, represented as MUI Chips.
 * It maintains a hidden input field to store the tags' values.
 *
 * @param props - The props for the component.
 * @returns The InputTags component.
 */
const InputTags: React.FC<Props> = (
    {
        id,
        name,
        helperText,
        required,
        ariaLabel,
        onTagChanges,
        tagType,
        initialTags
    }
) => {
    const theme = useTheme();
    const [inputValue, setInputValue] = useState<string>("");
    const [listItems, setListItems] = useState<string[]>(initialTags); // Initialize state with initial tags
    const tagRef = useRef<HTMLInputElement>(null);
    const tagPlaceholder = tagType ? tagType : "tags";

    /**
     * Handles the key down event for the input field.
     * Adds a new tag if Enter or comma is pressed.
     * Deletes the last tag if Backspace is pressed and input field is empty.
     *
     * @param event - The key down event.
     */
    const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>): void => {
        if (event.key === "Enter" || event.key === ",") {
            event.preventDefault();
            if (inputValue.trim()) {
                const newListItem = inputValue.trim();
                if (newListItem && !listItems.includes(newListItem)) {
                    const updatedListItems = [...listItems, newListItem];
                    setListItems(updatedListItems);
                    onTagChanges(updatedListItems);
                }
                setInputValue("");
            }
        } else if (event.key === "Backspace" && !inputValue) {
            setListItems((previousItems) => previousItems.slice(0, -1));
        }
    };

    /**
     * Handles the change event for the input field.
     * Updates the inputValue state with the current input value.
     *
     * @param event - The change event.
     */
    const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
        const { value } = event.target;
        setInputValue(value);
    };

    /**
     * Handles the delete event for a chip.
     * Removes the tag from the listItems state.
     *
     * @param itemsToDelete - The tag to be deleted.
     * @returns A function that deletes the specified tag.
     */
    const handleDelete = (itemsToDelete: string) => (): void => {
        const updatedListItems = listItems.filter(listItem => listItem !== itemsToDelete);
        setListItems(updatedListItems);
        onTagChanges(updatedListItems); // Notify parent component
    };

    /**
     * Updates the hidden input field value whenever listItems changes.
     */
    useEffect(() => {
        const hiddenInput = document.getElementById(id) as HTMLInputElement;
        if (hiddenInput) {
            hiddenInput.value = listItems.join(',');
        }
    }, [listItems, id]);

    useEffect(() => {
        // Check to ensure it doesn't add an empty string array
        if (initialTags) {
            if (initialTags.length > 0 && initialTags[0] !== "") {
                setListItems(initialTags);
            }
        }
    }, [initialTags]);

    return (
        <Box
            sx={{
                border: `1px solid ${theme.palette.divider}`,
                borderRadius: '4px',
                padding: 1,
            }}
        >
            <Box
                sx={{
                    padding: '4px',
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 0.5,
                    alignItems: 'center'
                }}
            >
                {listItems.length === 0 && (
                    <Chip
                        label={`Empty ${tagPlaceholder} placeholder`}
                    />
                )}
                {listItems.map((item, index) => (
                    <Chip
                        key={index}
                        label={item}
                        onDelete={handleDelete(item)}
                    />
                ))}
            </Box>
            <Box
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    mt: 2,
                }}
            >
                <TextField
                    autoComplete="off"
                    value={inputValue}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    inputRef={tagRef}
                    placeholder={`Enter ${tagPlaceholder}`}
                    variant='outlined'
                    multiline
                    sx={{ flex: '1 1 auto', minWidth: 100 }}
                    helperText={helperText}
                    aria-label={ariaLabel}
                />
                <input
                    type="hidden"
                    id={id}
                    name={`${name}`}
                    required={required}
                />
            </Box>
        </Box>
    );
}

export default InputTags;
