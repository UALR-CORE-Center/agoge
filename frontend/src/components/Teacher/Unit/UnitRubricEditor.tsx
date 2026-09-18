import EditIcon from "@mui/icons-material/Edit";
import {LoadingButton} from "@mui/lab";
import {
    Alert,
    Box,
    Button,
    TextField,
    Paper,
    Dialog,
    DialogTitle,
    DialogContent,
    TableContainer,
    Table,
    TableHead,
    TableRow,
    TableCell,
    TableBody,
    DialogActions,
    Skeleton, Typography, CircularProgress, styled, tableCellClasses
} from "@mui/material";
import React, { useState } from "react";
import { useAuthContext } from "../../../context/AuthContext";
import { Rubric } from "../../../services/Rubric/rubric.model";
import { rubricService } from "../../../services/Rubric/rubric.service";

interface UnitRubricEditorProps {
    buildId: string;
    isExpired: boolean;
    rubricEnabled?: boolean;
}

const UnitRubricEditor: React.FC<UnitRubricEditorProps> = (props) => {
    const { firebaseUser } = useAuthContext();
    const [open, setOpen] = useState(false);
    const [rubric, setRubric] = useState<Rubric | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [hasLoaded, setHasLoaded] = useState(false);
    const isBusy = isLoading || isGenerating || isSaving;

    const handleClickOpen = () => {
        if (props.rubricEnabled !== true) return;
        setOpen(true);
        loadRubric();
    };

    const handleClose = () => {
        setOpen(false);
    };

    const handleSave = async () => {
        if (props.rubricEnabled !== true || !rubric || !props.buildId || props.isExpired || isBusy) return;
        setIsSaving(true);
        setError(null);
        try {
            await rubricService.patch(props.buildId, {
                build_id: props.buildId,
                categories: rubric.categories,
                criteria: rubric.criteria,
                headers: rubric.headers
            });
            setOpen(false);
        } catch (error) {
            setError(error instanceof Error ? error.message : "Failed to save rubric. Please try again.");
        } finally {
            setIsSaving(false);
        }
    };

    const handleCriterionChange = (categoryIndex: number, headerIndex: number, value: string) => {
        setRubric(prevRubric => {
            if (!prevRubric) return prevRubric;

            const updatedCriteria = prevRubric.criteria.map((criterion) => {
                if (
                    criterion.category === prevRubric.categories[categoryIndex] &&
                    Number(criterion.index) === headerIndex // Convert crit.index to a number
                ) {
                    return { ...criterion, description: value };
                }
                return criterion;
            });

            return { ...prevRubric, criteria: updatedCriteria };
        });
    };

    // Opening or retrying a lookup never generates a rubric or uses AI credits.
    const loadRubric = async () => {
        if (props.rubricEnabled !== true || !firebaseUser.user || !props.buildId || isBusy) return;
        setIsLoading(true);
        setError(null);
        setRubric(null);
        setHasLoaded(false);
        try {
            const existingRubric = await rubricService.get(props.buildId);
            if (existingRubric?.categories?.length) {
                setRubric(existingRubric);
            }
            setHasLoaded(true);
        } catch (error) {
            setError(error instanceof Error ? error.message : "Could not load the rubric. Please try again.");
        } finally {
            setIsLoading(false);
        }
    };

    const generateRubric = async () => {
        if (props.rubricEnabled !== true || !firebaseUser.user || !props.buildId ||
            props.isExpired || isBusy || !hasLoaded || rubric) return;
        setIsGenerating(true);
        setError(null);
        try {
            const generatedRubric = await rubricService.generate_rubric(props.buildId, {
                id: props.buildId,
                confirm_ai_generation: true,
                total_points: 100,
                levels: ["Exemplary", "Proficient", "Developing", "Unsatisfactory"],
                categories: ["Configuration", "Documentation", "Communication", "Problem-solving"],
                headers: ["Exemplary (20-25 pts)", "Proficient (14-19 pts)", "Developing (7-13 pts)", "Unsatisfactory (0-6 pts)"]
            });
            setRubric(generatedRubric);
        } catch (error) {
            setError(error instanceof Error ? error.message : "Could not generate the rubric. Please try again.");
        } finally {
            setIsGenerating(false);
        }
    };

    const StyledTableCell = styled(TableCell)(({ theme }) => ({
        // This is for the Blue Header on the edit rubric
        [`&.${tableCellClasses.head}`]: {
            backgroundColor: theme.palette.primary.main,
            color: theme.palette.common.white,
        },
        // This is for the left hand side of the edit rubric
        "&.category-header": {
            backgroundColor: theme.palette.background.paper,
            fontWeight: "bold",
        },
    }));


    if (props.rubricEnabled !== true) return null;

    return (
        <Box>
            <Box sx={{ padding: 2 }}>
                <Button
                    variant="contained"
                    color="primary"
                    startIcon={<EditIcon />}
                    onClick={handleClickOpen}
                    disabled={isBusy}
                >
                    Manage Rubric
                </Button>
            </Box>

            <Dialog open={open} onClose={handleClose} fullWidth maxWidth="xl">
                <Paper elevation={2} sx={{ padding: 2 }}>
                    <DialogTitle>Edit Rubric</DialogTitle>
                    <DialogContent>
                        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                        {isGenerating ? (
                            // This is displayed when a rubric is generating for the first time
                            <Box position="relative" height={400}>
                                <Skeleton variant="rectangular" width="100%" height="100%"/>
                                <Box
                                    position="absolute"
                                    top="50%"
                                    left="50%"
                                    display="flex"
                                    alignItems="center"
                                    justifyContent="center"
                                    flexDirection="column"
                                    sx={{ transform: 'translate(-50%, -50%)' }}
                                >
                                    <CircularProgress />
                                    <Typography variant="h5" sx={{ mt: 2 }}>Generating Rubric...</Typography>
                                    <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
                                        This may take a few moments.
                                    </Typography>
                                </Box>
                            </Box>
                        ) : isLoading ? (
                            // General Loading while it is being fetched
                            <Skeleton variant="rectangular" width="100%" height={400} />
                        ) : rubric ? (
                            <TableContainer component={Paper}>
                                <Table sx={{ minWidth: 650 }} aria-label="rubric table">
                                    <TableHead>
                                        <TableRow>
                                            <StyledTableCell>Category</StyledTableCell>
                                            {rubric?.headers?.map((header, index) => (
                                                <StyledTableCell key={index}>{header}</StyledTableCell>
                                            ))}
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {rubric?.categories.map((category, categoryIndex) => (
                                            <TableRow key={categoryIndex}>
                                                <StyledTableCell className="category-header">{category}</StyledTableCell>
                                                {rubric.headers.map((header, headerIndex) => {
                                                    // Finds what entry on the criteria matches the current category and header index
                                                    const criterion = rubric.criteria.find(
                                                        (crit) =>
                                                            crit.category === category &&
                                                            Number(crit.index) === headerIndex
                                                    );

                                                    return (
                                                        <StyledTableCell key={headerIndex}>
                                                            <TextField
                                                                autoComplete="off"
                                                                fullWidth
                                                                multiline
                                                                value={criterion?.description || ""}
                                                                onChange={(e) =>
                                                                    handleCriterionChange(
                                                                        categoryIndex,
                                                                        headerIndex,
                                                                        e.target.value
                                                                    )
                                                                }
                                                                variant="outlined"
                                                                disabled={props.isExpired}
                                                            />
                                                        </StyledTableCell>
                                                    );
                                                })}
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        ) : hasLoaded ? (
                            <>
                                <Typography>No rubric has been created for this lab.</Typography>
                                {!props.isExpired && <Typography sx={{ mt: 1 }}>AI generation uses OpenAI API credits.</Typography>}
                            </>
                        ) : null}
                    </DialogContent>
                    <DialogActions>
                        {error && !hasLoaded && !isBusy && (
                            <Button variant="outlined" onClick={loadRubric}>
                                Retry loading
                            </Button>
                        )}
                        {props.isExpired ? (
                            <Button variant="contained" color="primary" onClick={handleClose}>
                                Close
                            </Button>
                        ): (
                            <>
                                <Button variant="contained" color="primary" onClick={handleClose}>
                                    Cancel
                                </Button>
                                {!rubric && hasLoaded && (
                                    <Button variant="outlined" onClick={generateRubric} disabled={isBusy}>
                                        Generate with AI
                                    </Button>
                                )}
                                <LoadingButton
                                    variant="contained"
                                    color="primary"
                                    onClick={handleSave}
                                    loading={isSaving}
                                    disabled={!rubric || isLoading || isGenerating}
                                >
                                    Confirm
                                </LoadingButton>
                            </>
                        )}
                    </DialogActions>
                </Paper>
            </Dialog>
        </Box>
    );
};

export default UnitRubricEditor;
