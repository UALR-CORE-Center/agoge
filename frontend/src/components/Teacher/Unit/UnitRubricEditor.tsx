import EditIcon from "@mui/icons-material/Edit";
import {LoadingButton} from "@mui/lab";
import {
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
import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuthContext } from "../../../context/AuthContext";
import { URL_ERROR } from "../../../router/urls";
import { Rubric } from "../../../services/Rubric/rubric.model";
import { rubricService } from "../../../services/Rubric/rubric.service";
import HttpError from "../../Common/Errors/HttpError";

interface UnitRubricEditorProps {
    buildId: string;
    isExpired: boolean;
}

const UnitRubricEditor: React.FC<UnitRubricEditorProps> = (props) => {
    const { firebaseUser } = useAuthContext();
    const navigate = useNavigate();
    const { build_id } = useParams<{ build_id: string }>();
    const [open, setOpen] = useState(false);
    const [rubric, setRubric] = useState<Rubric | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [hasGenerated, setHasGenerated] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    const handleClickOpen = () => {
        setOpen(true);
        if (!rubric) {
            generateRubric();
        } else {
            fetchData();
        }
    };

    const handleClose = () => {
        setOpen(false);
    };

    const handleSave = async () => {
        if (!rubric || !build_id || props.isExpired) return;
        setIsSaving(true);
        try {
            await rubricService.patch(build_id, {
                build_id,
                categories: rubric.categories,
                criteria: rubric.criteria,
                headers: rubric.headers
            });
            setOpen(false);
        } catch (error) {
            console.error("Failed to save rubric:", error);
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

    const handleError = useCallback(
        (error: HttpError) => {
            if ([404].includes(error.status)) {
                navigate(URL_ERROR, {
                    state: { status: error.status, message: error.message || "An error occurred" },
                });
            } else {
                navigate(URL_ERROR, {
                    state: { status: 500, message: "Something went wrong!" },
                });
            }
        },
        [navigate]
    );

    // Generates Rubric only if none exists
    const generateRubric = useCallback(async () => {
        // Helps against multiple generation attempts or if user isn't authed or no build_id is available
        if (!firebaseUser.user || !build_id || hasGenerated || isGenerating) return;
        setIsGenerating(true);
        try {
            const existingRubric = await rubricService.get(build_id);
            // In case there is a existingRubric and no length to it (empty but exists)
            if (!existingRubric || !existingRubric.categories?.length) {
                // TODO: This is using a hardcoded template, no other ones exist in database will need to update
                const rubricParams = {
                    id: props.buildId,
                    total_points: 100,
                    levels: ["Exemplary", "Proficient", "Developing", "Unsatisfactory"],
                    categories: ["Configuration", "Documentation", "Communication", "Problem-solving"],
                    criteria: [
                        {
                            description: "Configuration is fully complete, accurate, and optimized...",
                            index: "0",
                            category: "Configuration"
                        }
                    ],
                    headers: ["Exemplary (20-25 pts)", "Proficient (14-19 pts)", "Developing (7-13 pts)", "Unsatisfactory (0-6 pts)"]
                };
                await rubricService.generate_rubric(build_id, rubricParams);
                setHasGenerated(true);
            } else {
                setRubric(existingRubric);
            }
        } catch (error) {
            handleError(error as HttpError);
        } finally {
            setIsGenerating(false);
        }
    }, [firebaseUser.user, build_id, handleError]);

    const fetchData = useCallback(async () => {
        setIsLoading(true);
        try {
            const fetchedRubric = await rubricService.get(String(build_id));
            setRubric(fetchedRubric);
        } catch (error) {
            handleError(error as HttpError);
        } finally {
            setIsLoading(false);
        }
    }, [build_id, handleError]);

    useEffect(() => {
        generateRubric();
    }, [generateRubric]);

    useEffect(() => {
        if (!isGenerating && open) {
            fetchData();
        }
    }, [isGenerating, open]);

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


    return (
        <Box>
            <Box sx={{ padding: 2 }}>
                <Button
                    variant="contained"
                    color="primary"
                    startIcon={<EditIcon />}
                    onClick={handleClickOpen}
                >
                    Manage Rubric
                </Button>
            </Box>

            <Dialog open={open} onClose={handleClose} fullWidth maxWidth="xl">
                <Paper elevation={2} sx={{ padding: 2 }}>
                    <DialogTitle>Edit Rubric</DialogTitle>
                    <DialogContent>
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
                        ) : (
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
                        )}
                    </DialogContent>
                    <DialogActions>
                        {props.isExpired ? (
                            <Button variant="contained" color="primary" onClick={handleClose}>
                                Close
                            </Button>
                        ): (
                            <>
                                <Button variant="contained" color="primary" onClick={handleClose}>
                                    Cancel
                                </Button>
                                <LoadingButton
                                    variant="contained"
                                    color="primary"
                                    onClick={handleSave}
                                    loading={isSaving}
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