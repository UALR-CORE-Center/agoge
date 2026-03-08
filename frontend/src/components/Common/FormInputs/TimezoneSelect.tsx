import React, { useEffect, useState } from "react";
import { useTimezoneSelect, allTimezones, ITimezoneOption } from "react-timezone-select";
import { Select, InputLabel, MenuItem, SelectChangeEvent } from "@mui/material";

interface TimezoneSelectProps {
    labelStyle: 'original' | 'altName' | 'abbrev' | 'offsetHidden';
    defaultZone: string;
    displayValue: "UTC" | "GMT";
    onChange: (iTimezoneOption: ITimezoneOption) => void;
}

export const TimezoneSelect: React.FC<TimezoneSelectProps> = ({
    labelStyle,
    defaultZone,
    displayValue,
    onChange
}) => {
    const timezones = { ...allTimezones };
    const { options, parseTimezone } = useTimezoneSelect({ labelStyle, timezones, displayValue });
    const [selectedTimezone, setSelectedTimezone] = useState<string>(defaultZone);

    useEffect(() => {
        // Sync selectedTimezone with defaultZone prop
        setSelectedTimezone(defaultZone);
    }, [defaultZone]);

    const handleChange = (e: SelectChangeEvent<string>) => {
        const selectedValue = e.target.value;
        setSelectedTimezone(selectedValue);
        onChange(parseTimezone(selectedValue));
    };

    return (
        <>
            <InputLabel id="timezone-select-label">Timezone</InputLabel>
            <Select
                id="timezone-select"
                name="timezone"
                label="Timezone"
                value={selectedTimezone}
                onChange={handleChange}
            >
                {options.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                        {option.label}
                    </MenuItem>
                ))}
            </Select>
        </>
    );
};
