import React from "react";
import {Button, List, ListItem, ListItemText, Paper, Stack, Typography, useTheme} from "@mui/material";
import {SpecificationEdit} from "../../../../../services/Specification/specificationEdit.model";
import {ReviewCommonChildrenProps} from "./Review";
import {EditorForms} from "../utils/EditorTypes";
import {EditOutlined} from "@mui/icons-material";

import {
    EmptyListItem, EmptyListItemText,
    NestedReviewListItem,
    ReviewHeaderKey,
    ReviewHeaderValue,
    ReviewItemKey, ReviewItemKeyWrapper, ReviewItemValue,
    ReviewListHeader,
    ReviewListItem, ReviewSectionLabel
} from './ReviewCommonStyles';
import ChipListView from "../../../../Common/ChipListView";
import * as net from "net";
import ReviewItemValueOrSkeleton from "./ReviewItemValueOrSkeleton";

interface Props extends ReviewCommonChildrenProps {
    specification: SpecificationEdit | undefined,
    loading: boolean;
}


const AssessmentReview: React.FC<Props> = ({specification, loading, elevation, onNavigateToStep, styles={}, includeHeader=true}) => {
    const theme = useTheme();

    return (
        <Stack sx={styles} component={Paper} elevation={elevation}>
            {
                includeHeader &&
                <Stack sx={{paddingY: theme.spacing(1)}} direction={'row'} alignItems={'center'}
                       justifyContent={'space-between'}>
                    <ReviewSectionLabel variant={'h6'}>Assessment Review</ReviewSectionLabel>
                    <Button onClick={() => onNavigateToStep(EditorForms.Assessment)}
                            color={"info"}
                            size={'small'}
                            endIcon={<EditOutlined/>}>
                        Edit
                    </Button>
                </Stack>
            }

            <List sx={{padding: 0}} component={Paper} variant={'outlined'}>
                <ReviewListHeader>
                    <ReviewHeaderKey>Assessment</ReviewHeaderKey>
                    <ReviewHeaderValue>Values</ReviewHeaderValue>
                </ReviewListHeader>


                <ReviewListItem divider>
                    <ReviewItemKeyWrapper>
                        <ReviewItemKey size={'small'} label={"Assessment Script"}/>
                    </ReviewItemKeyWrapper>


                    <ReviewItemValueOrSkeleton
                        value={(specification?.assessment || specification?.lms_quiz)?.assessment_script?.script}
                        loading={loading}/>
                </ReviewListItem>

                <ReviewListItem divider>
                    <ReviewItemKeyWrapper>
                        <ReviewItemKey size={'small'} label={"Total Questions"}/>
                    </ReviewItemKeyWrapper>
                    <ReviewItemValueOrSkeleton
                        value={(specification?.assessment?.questions || specification?.lms_quiz?.questions || []).length}
                        loading={loading}/>
                </ReviewListItem>

                <ReviewListItem divider>
                    <ReviewItemKeyWrapper>
                        <ReviewItemKey size={'small'} label={"Questions"}/>
                    </ReviewItemKeyWrapper>
                    <ReviewItemValueOrSkeleton
                        value={specification?.assessment ?
                            JSON.stringify(specification?.assessment?.questions) : JSON.stringify(specification?.lms_quiz?.questions)}
                        loading={loading}/>

                </ReviewListItem>

            </List>


        </Stack>
    )
}

export default AssessmentReview;
