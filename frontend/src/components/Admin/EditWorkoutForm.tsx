import { TextField, Box, Button, Typography } from '@mui/material';
import React, { FC, useState, ChangeEvent } from 'react';
import { Workout } from '../../services/Workout/workout.model';


interface WorkoutFormProps {
    workout: Workout;   
    onChange: (workout: Workout) => void;
}

const EditWorkoutForm: FC<WorkoutFormProps> = ({workout, onChange }) => {
    const [formData, setFormData] = useState<Workout>(workout);

    const handleEmailChange = (e: ChangeEvent<HTMLInputElement>) => {
        console.log(e.target.value, "target value");
        const updatedFormData = { ...formData, student_email: e.target.value };
        setFormData(updatedFormData);
        onChange(updatedFormData);
    };

    return (
        <Box>
            <Typography variant="h6">Edit Student Email</Typography>

            <TextField
                autoComplete="email"
                margin="dense"
                label="Student Email"
                type="email"
                fullWidth
                value={formData.student_email}
                onChange={handleEmailChange}
            />
        </Box>
    );
}
export default EditWorkoutForm;