import React from "react";
import {Button, List, ListItem, ListItemText, Paper, Stack, Typography, useTheme} from "@mui/material";
import {SpecificationEdit} from "../../../../../services/Specification/specificationEdit.model";
import {ReviewCommonChildrenProps} from "./Review";
import {EditorForms} from "../utils/EditorTypes";
import {EditOutlined} from "@mui/icons-material";

import {
    ReviewHeaderKey,
    ReviewHeaderValue,
    ReviewItemKey, ReviewItemKeyWrapper, ReviewItemValue,
    ReviewListHeader,
    ReviewListItem, ReviewSectionLabel,

} from './ReviewCommonStyles';
import ChipListView from "../../../../Common/ChipListView";
import ReviewItemValueOrSkeleton from "./ReviewItemValueOrSkeleton";

interface Props extends ReviewCommonChildrenProps {
    specification: SpecificationEdit | undefined,
    loading: boolean;
}


const SummaryReview: React.FC<Props> = ({specification, elevation, loading, onNavigateToStep,styles={}, includeHeader = true}) => {
    const theme = useTheme();

    return (
        <Stack sx={styles} component={Paper} elevation={elevation}>

            {
                includeHeader &&
            <Stack sx={{paddingY: theme.spacing(1)}} direction={'row'} alignItems={'center'}
                   justifyContent={'space-between'}>
                <ReviewSectionLabel variant={'h6'}>Summary Review</ReviewSectionLabel>
                <Button onClick={() => onNavigateToStep(EditorForms.Summary)}
                        size={'small'}
                        color={"info"}
                        endIcon={<EditOutlined/>}>
                    Edit
                </Button>
            </Stack>
            }

            <List sx={{padding: 0}} component={Paper} variant={'outlined'}>
                <ReviewListHeader>
                    <ReviewHeaderKey>Keys</ReviewHeaderKey>
                    <ReviewHeaderValue>Values</ReviewHeaderValue>
                </ReviewListHeader>

                <ReviewListItem divider>
                    <ReviewItemKeyWrapper>
                        <ReviewItemKey size={'small'} label={"Name"}/>
                    </ReviewItemKeyWrapper>
                    <ReviewItemValueOrSkeleton value={specification?.summary?.name} loading={loading}/>
                </ReviewListItem>

                <ReviewListItem divider>
                    <ReviewItemKeyWrapper>
                        <ReviewItemKey size={'small'} label={"Author"}/>
                    </ReviewItemKeyWrapper>
                    <ReviewItemValueOrSkeleton value={specification?.summary?.author} loading={loading}/>
                </ReviewListItem>

                <ReviewListItem divider>
                    <ReviewItemKeyWrapper>
                        <ReviewItemKey size={'small'} label={"Description"}/>
                    </ReviewItemKeyWrapper>

                    <ReviewItemValueOrSkeleton value={specification?.summary?.description} loading={loading}/>
                </ReviewListItem>

                <ReviewListItem divider>
                    <ReviewItemKeyWrapper>
                        <ReviewItemKey size={'small'} label={"Teacher Instructions URL"}/>
                    </ReviewItemKeyWrapper>

                    <ReviewItemValueOrSkeleton value={specification?.summary?.teacher_instructions_url}
                                               loading={loading}/>
                </ReviewListItem>

                <ReviewListItem divider>
                    <ReviewItemKeyWrapper>
                        <ReviewItemKey size={'small'} label={"Student Instructions URL"}/>
                    </ReviewItemKeyWrapper>

                    <ReviewItemValueOrSkeleton value={specification?.summary?.student_instructions_url}
                                               loading={loading}/>
                </ReviewListItem>

                <ReviewListItem divider>
                    <ReviewItemKeyWrapper>
                        <ReviewItemKey size={'small'} label={"Hourly Cost"}/>
                    </ReviewItemKeyWrapper>
                    <ReviewItemValueOrSkeleton
                        value={specification?.summary?.hourly_cost}
                        loading={loading}/>
                </ReviewListItem>

                <ReviewListItem divider>
                    <ReviewItemKeyWrapper>
                        <ReviewItemKey size={'small'} label={"Tags"}/>
                    </ReviewItemKeyWrapper>
                    <ReviewItemValueOrSkeleton
                        value={<ChipListView values={specification?.summary?.tags || []}/>}
                        loading={loading}/>
                </ReviewListItem>
            </List>


        </Stack>
    )
}

export default SummaryReview;
