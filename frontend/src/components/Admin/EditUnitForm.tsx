import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import {TextField, Box, Button, IconButton, Typography, Tooltip} from '@mui/material';
import React, { FC, useState, ChangeEvent } from 'react';
import { Unit } from '../../services/Unit/unit.model';

interface UnitFormProps {
    unit: Unit;
    onChange: (unit: Unit) => void;
}

const EditUnitForm: FC<UnitFormProps> = ({ unit, onChange }) => {
    const [formData, setFormData] = useState<Unit>(unit);
    const instructorFields = formData.instructor_id ? (formData.instructor_id).toString().split(',') : [];

    const handleInstructorChange = (index: number) => (e: ChangeEvent<HTMLInputElement>) => {
        const newInstructors = formData.instructor_id ? (formData.instructor_id).toString().split(',') : [];
        newInstructors[index] = e.target.value;
        const updatedFormData = { ...formData, instructor_id: newInstructors.join(',') };
        setFormData(updatedFormData);
        onChange(updatedFormData);
    };

    const addInstructorField = () => {
        const newInstructors = formData.instructor_id ? (formData.instructor_id).toString().split(',') : [];
        newInstructors.push('');
        const updatedFormData = { ...formData, instructor_id: newInstructors.join(',') };
        setFormData(updatedFormData);
        onChange(updatedFormData);
    };

    const removeInstructorField = (index: number) => () => {
        const newInstructors = formData.instructor_id ? (formData.instructor_id).toString().split(',') : [];
        newInstructors.splice(index, 1);
        const updatedFormData = { ...formData, instructor_id: newInstructors.join(',') };
        setFormData(updatedFormData);
        onChange(updatedFormData);
    };

    return (
        <>
            <Box>
                <Typography variant="h6">Instructors</Typography>
                {instructorFields.map((instructor, index) => (
                    <Box key={index} display="flex" alignItems="center" mb={2}>
                        <TextField
                            margin="dense"
                            label={`Instructor ${index + 1}`}
                            type="text"
                            name="instructor_id[]"
                            fullWidth
                            value={instructor}
                            onChange={handleInstructorChange(index)}
                            autoComplete="email"
                        />
                        <Tooltip title="Remove instructor" placement="top" arrow>
                            <IconButton onClick={removeInstructorField(index)} aria-label="Remove instructor">
                                <DeleteIcon />
                            </IconButton>
                        </Tooltip>
                    </Box>
                ))}
                <Button
                    variant="contained"
                    color={"primary"}
                    startIcon={<AddIcon />}
                    onClick={addInstructorField}
                >
                    Add Instructor
                </Button>
            </Box>
        </>
    );
};

export default EditUnitForm;
