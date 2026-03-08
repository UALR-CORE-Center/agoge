import {
    Box,
    Dialog,
    DialogTitle,
    DialogContent,
    Button,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    FormGroup,
    FormControlLabel,
    Checkbox,
    Typography,
    Divider,
} from '@mui/material';
import Alert from "@mui/material/Alert";
import DialogActions from "@mui/material/DialogActions";
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFnsV3';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import React, { useEffect, useState, useRef } from 'react';
import { TeachingConcepts } from "../../../../services/Specification/specification.model";
import { SafeAgogeUser, UserCourses } from "../../../../services/User/user.model";
import { userService } from '../../../../services/User/user.service';
import NumberInputField from '../../../Common/FormInputs/NumberInputField';
import { TagChip } from "../TagChips";

interface WorkoutModalProps {
    open: boolean;
    user: SafeAgogeUser | null;
    onClose: () => void;
    onSubmit: (formData: any) => void;
    selectedRow: any;
}

export const WorkoutModal: React.FC<WorkoutModalProps> = (props) => {
    const { open, onClose, onSubmit, selectedRow, user } = props;
    const hasMounted = useRef(false);
    const [agogeUser, setSettingsData] = useState<any>();
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [courses, setCourses] = useState<UserCourses>({});
    const [displayedCourses, setDisplayedCourses] = useState([{ value: '', label: '-- Select a LMS --' }]);
    const [displayedCodes, setDisplayedCodes] = useState([{ value: '', label: '-- Select a Course Code --' }]);

    const userId = user ? user.uid : "";
    const summary = selectedRow.summary;
    const description = summary?.description;
    const summaryTags: TeachingConcepts[] = summary?.tags ? summary.tags : [];
    const defaultTimezone = user?.timezone || "America/Chicago";
    const defaultDate = new Date();
    defaultDate.setHours(23, 59, 0, 0);
    const [formData, setFormData] = useState({
        expires: defaultDate,
        timezone: defaultTimezone,
        build_count: 1,
        lms_integration: !!selectedRow?.lms_quiz,
        lms_type: '',
        lms_course_code: '',
        registration_required: false,
        build_file: selectedRow.id,
        lms_allowed_attempts: 1
    });

    useEffect(() => {
        const fetchSettings = async () => {
            try {
                const fetchedAgogeUser = await userService.get(userId);
                setSettingsData(fetchedAgogeUser);
            } catch (error) {
                console.log("Failed to fetch user data.");
                console.log(error);
            }
        };
        fetchSettings();
    }, [userId]);

    useEffect(() => {
        const fetchCourses = async () => {
            try {
                const fetchedCourses = await userService.get_courses(userId);
                setCourses(fetchedCourses);
                if (!hasMounted.current) {
                    const courseOptions = [];
                    if (fetchedCourses.canvas) {
                        courseOptions.push({ value: 'canvas', label: 'Canvas' });
                    }
                    if (fetchedCourses.blackboard) {
                        courseOptions.push({ value: 'blackboard', label: 'Blackboard' });
                    }
                    if (fetchedCourses.classroom) {
                        courseOptions.push({ value: 'classroom', label: 'Classroom' });
                    }
                    setDisplayedCourses([{ value: '', label: '-- Select a LMS --' }, ...courseOptions]);
                    hasMounted.current = true;
                }
            } catch (error) {
                console.log(error);
                console.log("Failed to fetch LMS data.");
            }
        };
        fetchCourses();
    }, [userId]);

    const handleDateChange = (date: Date | null) => {
        if (date) {
            setFormData(prevFormData => ({
                ...prevFormData,
                expires: date
            }));
        }
    };

    const handleSelectChange = (event: any) => {
        const { name, value } = event.target;
        setFormData(prevFormData => ({
            ...prevFormData,
            [name]: value,
        }));

        if (name === "lms_type" && value !== "") {
            setDisplayedCodes([{ value: '', label: '-- Select a Course Code --' }]);
            const selectedCourses = courses[value as keyof UserCourses];
            if (selectedCourses) {
                selectedCourses.forEach(course => {
                    const newOption = { value: course.id, label: course.name };
                    setDisplayedCodes(prevOptions => [...prevOptions, newOption]);
                });
            }
        }
        if (name === "lms_type" && value === "") {
            setDisplayedCodes([{ value: '', label: '-- Select a Course Code --' }]);
        }
    };

    const handleNumberChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = event.target;
        if (/^\d*$/.test(value)) {
            setFormData(prevFormData => ({
                ...prevFormData,
                [name]: value === '' ? 0 : parseInt(value),
            }));
        }
    };

    const handleCheckboxChange = () => {
        setFormData(prevFormData => ({
            ...prevFormData,
            lms_integration: !prevFormData.lms_integration,
        }));
    };

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (validateForm()) {
            setErrorMessage(null);
            onSubmit(formData);
        } else {
            setErrorMessage("Please fill out all required fields.");
        }
    };

    const validateForm = () => {
        let valid = true;
        if (!formData.expires || formData.expires.toUTCString() === "Invalid Date") {
            valid = false;
        }
        if (!formData.timezone) {
            valid = false;
        }
        if (formData.build_count <= 0) {
            valid = false;
        }
        if (formData.lms_integration) {
            if (!formData.lms_type) {
                valid = false;
            }
            if (!formData.lms_course_code) {
                valid = false;
            }
        }
        return valid;
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
            <DialogTitle>
                {summary.name}#{selectedRow.discriminator}
                <Divider />
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                    {summaryTags && summaryTags.length > 0 && (
                        summaryTags.map(tag => (
                            <TagChip key={tag.id} chipType={tag.name} />
                        ))

                    )}
                </Box>
            </DialogTitle>
            <DialogContent>
                <Typography>
                    {description}
                </Typography>
                <Divider sx={{my: 2}}/>
                {errorMessage && (
                    <Alert severity="error" sx={{ mb: 2 }}>
                        {errorMessage}
                    </Alert>
                )}
                <Box
                    component="form"
                    onSubmit={handleSubmit}
                    noValidate
                    autoComplete="off"
                    display={"flex"}
                    flexDirection={"column"}
                >
                    <FormControl margin={"normal"} required={true}>
                        <LocalizationProvider
                            dateAdapter={AdapterDateFns}
                        >
                            <DateTimePicker
                                label={"Expires*"}
                                disablePast
                                value={formData.expires}
                                onChange={handleDateChange}
                                closeOnSelect={false}
                                defaultValue={defaultDate}
                            />
                        </LocalizationProvider>
                    </FormControl>

                    <FormControl margin={"normal"} required={true}>
                        <NumberInputField
                            name={"build_count"}
                            min={1}
                            max={100}
                            label={"Max number of students*"}
                            value={formData.build_count}
                            onChange={handleNumberChange}
                            helperText={`Max number of students allowed to join (non-LMS builds only)`}
                        />
                    </FormControl>

                    <FormGroup>
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={formData.lms_integration}
                                    onChange={handleCheckboxChange}
                                />
                            }
                            label="Build with LMS"
                        />
                    </FormGroup>

                    <FormControl margin={"normal"} required={formData.lms_integration}>
                        <InputLabel id={"lms-select-label"}>Learning Management System</InputLabel>
                        <Select
                            id={"lms-select"}
                            name={"lms_type"}
                            label={"Learning Management System (LMS)"}
                            value={formData.lms_type}
                            onChange={handleSelectChange}
                            disabled={!formData.lms_integration}
                        >
                            {displayedCourses.map((option) => (
                                <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <FormControl margin={"normal"} required={formData.lms_integration}>
                        <InputLabel id={"course-code-label"}>Course Code</InputLabel>
                        <Select
                            id={"course-code"}
                            name="lms_course_code"
                            label={"Course Code"}
                            value={formData.lms_course_code}
                            onChange={handleSelectChange}
                            disabled={!formData.lms_integration || !formData.lms_type}
                        >
                            {displayedCodes.map((option) => (
                                <MenuItem key={option.value} value={option.value}>
                                    {option.label}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <DialogActions >
                        <Button
                            color={"error"}
                            onClick={() => {
                                onClose();
                            }}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            variant="contained"
                            color="primary"
                        >
                            Build Workout!
                        </Button>
                    </DialogActions>
                </Box>
            </DialogContent>
        </Dialog>
    );
}
