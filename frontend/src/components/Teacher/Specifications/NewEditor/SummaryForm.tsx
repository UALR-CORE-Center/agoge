import LoadingButton from "@mui/lab/LoadingButton";
import {
    Button,
    Dialog,
    DialogContent,
    DialogTitle, IconButton,
    Stack,
    TextField, Tooltip,
    Typography,
    useTheme
} from "@mui/material";
import DialogActions from "@mui/material/DialogActions";
import React, {useState} from "react";
import {IUseFormHook} from "../../../../hooks/useForm";
import {DocSummary} from "../../../../services/Documents/docs.model";
import {docsService} from "../../../../services/Documents/docs.service";
import {TeachingConcept} from "../../../../services/Specification/specificationEdit.model";
import {mapTeachingConcepts, TeachingConcepts, UnitType} from "../../../../types/BuildConstants";
import ChipListView from "../../../Common/ChipListView";
import {CommonEditorChildrenProps, SummaryFormKeys} from "./utils/EditorTypes";
import {
    FormAutocompleteField,
    FormFields,
    FormGroup, FormGroupOutline, FormMultiSelect,
    FormTextField,
    StyledFormFieldLabel,
} from "./utils/FormFields";
import EditIcon from "@mui/icons-material/Edit";
import {NoteAdd} from "@mui/icons-material";


interface Props extends CommonEditorChildrenProps {
    formHook: IUseFormHook;
    teacherFiles: DocSummary[];
    studentFiles: DocSummary[];
}


const SummaryForm: React.FC<Props> = (props: Props) => {
    const theme = useTheme();
    const [conceptLookup, setLookup] = useState(mapTeachingConcepts(Object.values(TeachingConcepts)))
    // These are used to handle creating a new instruction file
    const [loading, setLoading] = useState(false);
    const [openDialog, setOpenDialog] = useState<null | "teacher" | "student">(null);
    const [fileName, setFileName] = useState("");

    const handleCreateNewFile = async () => {
        if (!fileName.trim() || !openDialog) return;

        setLoading(true);
        try {
            const response = await docsService.create(fileName, openDialog);
            if (response?.uid) {
                const newFile = { uid: response.uid, name: fileName };
                if (openDialog === "teacher") {
                    props.formHook.handleInputChange(SummaryFormKeys.summaryTeacherInstructions, newFile);
                } else if (openDialog === "student") {
                    props.formHook.handleInputChange(SummaryFormKeys.summaryStudentInstructions, newFile);
                }
                window.open(`/documents/edit/${response.uid}`, "_blank");
            }
        } catch (error) {
            console.error("Failed to create new instruction:", error);
        }
        setLoading(false);
        setOpenDialog(null);
        setFileName("");
    };

    const handleRemoveTeachingConcept = (concept: TeachingConcept): void => {
        const formField = props.formHook.form![SummaryFormKeys.summaryTeachingConcepts];
        const updated = formField.value.filter((item: TeachingConcept | string) => {
            if (typeof item === 'string') {
                // Compare directly with the concept name if the item is a string
                return item.toLowerCase() !== concept.name.toLowerCase();
            } else {
                // Compare the name property if the item is a TeachingConcept object
                return item.name.toLowerCase() !== concept.name.toLowerCase();
            }
        });

        props.formHook.handleInputChange(SummaryFormKeys.summaryTeachingConcepts, updated);
    }

    const handleUpdateTeachingConcept = (concepts: (TeachingConcept | string)[]): void => {
        if (concepts.length > 0 && typeof concepts[concepts.length - 1] == 'string') {
            const value: string = concepts[concepts.length - 1] as string;
            const id = value.split(' ').join('_').toLowerCase()
            const newConcept = {
                id: id,
                name: value
            };

            concepts.splice(concepts.length - 1, 1, newConcept);
        }

        props.formHook.handleInputChange(SummaryFormKeys.summaryTeachingConcepts, concepts);
    }


    const teachingConceptExists = (concept: string): boolean => {
        return props.formHook.getFormField(SummaryFormKeys.summaryTeachingConcepts)?.value
            .map((tc: TeachingConcept) => tc.name).includes(concept)
    }

    return (
        <FormFields>
            <FormGroupOutline showOverlay={props.disableForm}>
                <FormGroup>
                    <StyledFormFieldLabel>Name</StyledFormFieldLabel>
                    <FormTextField
                        formKey={SummaryFormKeys.summaryName}
                        fieldFn={(key) => props.formHook.getFormField(key)}
                        disabled={props.disableForm}
                        onInputChange={(field, value) => {
                            props.formHook.handleInputChange(field, value)
                        }}
                    />
                </FormGroup>
            </FormGroupOutline>

            <FormGroupOutline showOverlay={props.disableForm}>
                <FormGroup>
                    <StyledFormFieldLabel>Author</StyledFormFieldLabel>
                    <FormTextField
                        formKey={SummaryFormKeys.summaryAuthor}
                        fieldFn={(key) => props.formHook.getFormField(key)}
                        disabled={props.disableForm}
                        onInputChange={(field, value) => {
                            props.formHook.handleInputChange(field, value)
                        }}
                    />
                </FormGroup>
            </FormGroupOutline>


            <FormGroupOutline showOverlay={props.disableForm}>

                <FormGroup>
                    <StyledFormFieldLabel>Unit Type</StyledFormFieldLabel>
                    <Stack>
                        <Typography variant={'subtitle2'}>Defines the type of unit setup.</Typography>
                        <ul style={{margin: theme.spacing(.5)}}>
                            <li>
                                <Typography variant={'subtitle2'}>
                                    'Solo' means each student gets their own isolated workout lab, independent of
                                    others.
                                </Typography>
                            </li>
                            <li>
                                <Typography variant={'subtitle2'}>
                                    'Community' means all workouts are built within a shared network environment, where
                                    resources might be shared among students.
                                </Typography>
                            </li>
                        </ul>
                    </Stack>

                    <FormAutocompleteField
                        options={Object.values(UnitType)}
                        formKey={SummaryFormKeys.summaryUnitType}
                        disabled={props.disableForm}
                        fieldFn={(key) => props.formHook.getFormField(key)}
                        onInputChange={(field, value) => {
                            props.formHook.handleInputChange(field, value)
                        }}
                    />
                </FormGroup>
            </FormGroupOutline>


            <FormGroupOutline showOverlay={props.disableForm}>

                <Stack gap={2}>
                    <FormGroup>
                        <StyledFormFieldLabel>Teacher Instructions</StyledFormFieldLabel>
                        <Stack direction="row" spacing={1} alignItems="center">
                            <FormAutocompleteField
                                options={props.teacherFiles}
                                getOptionLabel={(option) => option.name ?? "Unknown"}
                                formKey={SummaryFormKeys.summaryTeacherInstructions}
                                disabled={props.disableForm}
                                fieldFn={(key) => props.formHook.getFormField(key)}
                                onInputChange={(field, value) => {
                                    props.formHook.handleInputChange(field, value);
                                }}
                                sx={{ flexGrow: 1 }}
                            />
                            {props.formHook.getFormField(SummaryFormKeys.summaryTeacherInstructions)?.value && (
                                <Tooltip title={"Edit"} placement={"top"}>
                                    <IconButton
                                        onClick={() => {
                                            const selectedFile = props.formHook.getFormField(SummaryFormKeys.summaryTeacherInstructions)?.value;
                                            if (selectedFile?.uid) {
                                                window.open(`/documents/edit/${selectedFile.uid}`, "_blank");
                                            }
                                        }}
                                    >
                                        <EditIcon />
                                    </IconButton>
                                </Tooltip>
                            )}
                            <Tooltip title={"Create New Teacher File"} placement="top">
                                <IconButton
                                    onClick={() => setOpenDialog("teacher")}
                                    disabled={props.disableForm || loading}
                                >
                                    <NoteAdd />
                                </IconButton>
                            </Tooltip>
                        </Stack>
                    </FormGroup>

                    <FormGroup>
                        <StyledFormFieldLabel>Student Instructions</StyledFormFieldLabel>
                        <Stack direction="row" spacing={1} alignItems="center">
                            <FormAutocompleteField
                                options={props.studentFiles}
                                getOptionLabel={(option) => option.name ?? "Unknown"}
                                formKey={SummaryFormKeys.summaryStudentInstructions}
                                disabled={props.disableForm}
                                fieldFn={(key) => props.formHook.getFormField(key)}
                                onInputChange={(field, value) => {
                                    props.formHook.handleInputChange(field, value);
                                }}
                                sx={{ flexGrow: 1 }}
                            />
                            {props.formHook.getFormField(SummaryFormKeys.summaryStudentInstructions)?.value && (
                                <Tooltip title={"Edit"} placement={"top"}>
                                    <IconButton
                                        aria-label="Edit teacher instructions"
                                        onClick={() => {
                                            const selectedFile = props.formHook.getFormField(SummaryFormKeys.summaryStudentInstructions)?.value;
                                            if (selectedFile?.uid) {
                                                window.open(`/documents/edit/${selectedFile.uid}`, "_blank");
                                            }
                                        }}
                                    >
                                        <EditIcon />
                                    </IconButton>
                                </Tooltip>
                            )}
                            <Tooltip title={"Create New Student File"} placement="top">
                                <IconButton
                                    onClick={() => setOpenDialog("student")}
                                    disabled={props.disableForm || loading}
                                >
                                    <NoteAdd />
                                </IconButton>
                            </Tooltip>
                        </Stack>
                    </FormGroup>
                </Stack>
            </FormGroupOutline>

            <FormGroupOutline showOverlay={props.disableForm}>

                <FormGroup>
                    <StyledFormFieldLabel>Description</StyledFormFieldLabel>
                    <FormTextField
                        placeholder={'Brief lab description up to 200 characters'}
                        formKey={SummaryFormKeys.summaryDescription}
                        disabled={props.disableForm}
                        fieldFn={(key) => props.formHook.getFormField(key)}
                        onInputChange={(field, value) => {
                            props.formHook.handleInputChange(field, value)
                        }}
                    />
                </FormGroup>
            </FormGroupOutline>


            <FormGroupOutline showOverlay={props.disableForm}>

                <FormGroup>
                    <StyledFormFieldLabel>Teaching Concepts</StyledFormFieldLabel>

                    <Stack gap={1}>
                        <Typography variant={"subtitle2"}>Optional, at a glace lab descriptors</Typography>
                        <ChipListView
                            values={props.formHook.getFormField(SummaryFormKeys.summaryTeachingConcepts)?.value || []}
                            renderLabel={(r: TeachingConcept) => r.name}
                            onRemove={(value) => handleRemoveTeachingConcept(value)}
                        />
                    </Stack>
                    <FormMultiSelect
                        renderValueOverrideText={"Select Concepts"}
                        options={Object.values(TeachingConcepts)}
                        disabled={props.disableForm}
                        isSelected={(value) => teachingConceptExists(value)}
                        onSelection={(value: (TeachingConcept | string)[]) => {
                            handleUpdateTeachingConcept(value);
                        }}
                        onRemove={(values: string[], value: string) => {
                            handleRemoveTeachingConcept({id: value, name: value})
                        }}
                        placeholder={'Optional, at a glance lab descriptors'}
                        formKey={SummaryFormKeys.summaryTeachingConcepts}
                        fieldFn={(key) => props.formHook.getFormField(key)}
                        onInputChange={(field, value) => {
                            props.formHook.handleInputChange(field, value)
                        }}
                    />
                </FormGroup>
                <Dialog open={openDialog !== null} onClose={() => setOpenDialog(null)}>
                    <DialogTitle>Create New {openDialog === "teacher" ? "Teacher" : "Student"} Instruction</DialogTitle>
                    <DialogContent>
                        <TextField
                            autoFocus
                            fullWidth
                            label="File Name"
                            defaultValue={""}
                            value={fileName}
                            onChange={(e) => setFileName(e.target.value)}
                            margin="dense"
                            slotProps={{ htmlInput: { maxLength: 30 } }}
                        />
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setOpenDialog(null)} disabled={loading}>
                            Cancel
                        </Button>
                        <LoadingButton
                            onClick={handleCreateNewFile}
                            loading={loading}
                            disabled={!fileName.trim()}
                            variant="contained"
                            color="primary"
                        >
                            Create
                        </LoadingButton>
                    </DialogActions>
                </Dialog>
            </FormGroupOutline>

        </FormFields>
    )
}

export default SummaryForm;