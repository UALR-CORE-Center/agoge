import React, {useState} from "react";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Box,
    Button, IconButton,
    Paper,
    Stack,
    Typography,
    useTheme
} from "@mui/material";
import {SpecificationEdit} from "../../../../../services/Specification/specificationEdit.model";
import {EditorForms} from "../utils/EditorTypes";
import SummaryReview from "./SummaryReview";
import {useClipboard} from "../../../../../hooks/useClipboard";
import NetworkReview from "./NetworkReview";
import ServerReview from "./ServerReview";
import {Assessment, ContentCopy, ExpandLess, ExpandMore} from "@mui/icons-material";
import {ReviewSectionLabel} from "./ReviewCommonStyles";
import WebAppReview from "./WebAppReview";
import AssessmentReview from "./AssessmentReview";
import {SxProps} from "@mui/system";
import {Theme} from "@mui/material/styles/createTheme";

interface Props {
    specification: SpecificationEdit | undefined
    onNavigateToStep: (form: EditorForms) => void;


}

export interface ReviewCommonChildrenProps {
    onNavigateToStep: (form: EditorForms) => void;
    elevation: number;
    includeHeader?: boolean;
    styles?: SxProps<Theme>;
}

const Review: React.FC<Props> = ({specification, onNavigateToStep}) => {
    const [jsonExpanded, setJsonExpanded] = useState(false);
    const clipboard = useClipboard();

    // todo indicate some loader for Images API & Spec Api Call

    const theme = useTheme();
    const elevation = 8;
    const loading = specification == undefined;
    const defaultSX = {padding: 2};
    return (
        <Stack sx={{padding: theme.spacing(1)}} gap={2}>
            <Accordion disabled={loading} expanded={jsonExpanded} elevation={elevation}>
                <AccordionSummary
                    id={`json-panel-header`}
                    aria-controls={`json-panel-header`}
                    aria-expanded={jsonExpanded}
                    aria-label={
                        jsonExpanded ? "Collapse JSON" : "Expand JSON"
                    }
                    onClick={() => setJsonExpanded((prev) => !prev)}
                >
                    <Stack sx={{width: '100%'}} direction={'row'} alignItems={'center'}
                           justifyContent={'space-between'}>
                        <Stack direction={'row'} alignItems={'center'} gap={1}>
                            <ReviewSectionLabel variant={'h6'}>JSON</ReviewSectionLabel>
                            <IconButton disabled={loading} color={'primary'}>
                                {jsonExpanded ? <ExpandLess/> : <ExpandMore/>}
                            </IconButton>
                        </Stack>

                        <Button onClick={(e) => {
                            e.stopPropagation();
                            clipboard.copy(JSON.stringify(specification))
                        }} size={'small'} variant={'contained'} sx={{backgroundColor:'secondary.dark'}} endIcon={<ContentCopy/>}>
                            Copy JSON
                        </Button>
                    </Stack>
                </AccordionSummary>
                <AccordionDetails>
                    <Paper sx={{overflow: 'hidden'}} elevation={0}>
                        <Box sx={{overflowX: 'scroll', padding: theme.spacing(1)}}>
                            <Typography variant={'caption'}>
                                <pre>{JSON.stringify(specification, null, 2)}</pre>
                            </Typography>
                        </Box>
                    </Paper>
                </AccordionDetails>
            </Accordion>

            <SummaryReview
                elevation={elevation}
                loading={loading}
                styles={defaultSX}
                specification={specification}
                onNavigateToStep={onNavigateToStep}/>

            <NetworkReview elevation={elevation} loading={loading} styles={defaultSX}
                           specification={specification} onNavigateToStep={onNavigateToStep} />

            <ServerReview elevation={elevation} loading={loading} specification={specification}
                          onNavigateToStep={onNavigateToStep} styles={defaultSX}/>
            <WebAppReview elevation={elevation} loading={loading} specification={specification}
                          onNavigateToStep={onNavigateToStep} styles={defaultSX}/>
            <AssessmentReview elevation={elevation} loading={loading} specification={specification}
                              onNavigateToStep={onNavigateToStep} styles={defaultSX}/>

        </Stack>
    )
}

export default Review;
