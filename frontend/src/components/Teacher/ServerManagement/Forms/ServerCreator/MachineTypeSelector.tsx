import {
    InputLabel,
    MenuItem,
    Select,
} from "@mui/material";
import { SelectChangeEvent } from "@mui/material/Select";
import React, { useState, useEffect } from "react";

interface MachineTypeSelectorProps {
    selectedValue?: string;
}

const machineTypes = [
    { value: 'e2-micro', description: 'e2-micro - 1vCPU, 4GB Memory' },
    { value: 'e2-medium', description: 'e2-medium - 2vCPU, 4GB Memory' },
    { value: 'e2-standard-2', description: 'e2-standard-2 - 2vCPU, 8GB Memory' },
    { value: 'e2-standard-4', description: ' e2-standard-4 - 4vCPU, 16GB Memory' },
    { value: 'e2-standard-8', description: 'e2-standard-8 - 8vCPU, 32GB Memory' },
];

const MachineTypeSelector: React.FC<MachineTypeSelectorProps> = (
    { selectedValue }
) => {
    const [selectedMachineType, setSelectedMachineType] = useState("");

    useEffect(() => {
        if (
            selectedValue
            && machineTypes.some(machine => machine.value === selectedValue)
        ) {
            setSelectedMachineType(selectedValue);
        }
    }, [selectedValue]);

    const handleChange = (event: SelectChangeEvent) => {
        setSelectedMachineType(event.target.value as string);
    };

    return (
        <>
            <InputLabel id="machine-type-select-label">Select machine type*</InputLabel>
            <Select
                id="machine-type-select"
                labelId="machine-type-select-label"
                name={"machine_type"}
                value={selectedMachineType}
                label="Select machine type"
                onChange={handleChange}
                variant="outlined"
                required
                aria-required={true}
            >
                {machineTypes.map((machine) => (
                    <MenuItem key={machine.value} value={machine.value}>
                        {machine.description}
                    </MenuItem>
                ))}
            </Select>
        </>
    );
};

export default MachineTypeSelector;