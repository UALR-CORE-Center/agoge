import React from "react";
import {Button, List, ListItem, ListItemText, Paper, Skeleton, Stack, Typography, useTheme} from "@mui/material";
import {SpecificationEdit} from "../../../../../services/Specification/specificationEdit.model";
import {ReviewCommonChildrenProps} from "./Review";
import {EditorForms} from "../utils/EditorTypes";
import {EditOutlined} from "@mui/icons-material";

import {
    EmptyListItem,
    EmptyListItemText,
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


const NetworkReview: React.FC<Props> = ({specification, loading, elevation, onNavigateToStep, styles={}, includeHeader=true}) => {
    const theme = useTheme();

    return (
        <Stack sx={styles} component={Paper} elevation={elevation}>
            {
                includeHeader &&
                <Stack sx={{paddingY: theme.spacing(1)}} direction={'row'} alignItems={'center'}
                       justifyContent={'space-between'}>
                    <ReviewSectionLabel variant={'h6'}>Web Application Review</ReviewSectionLabel>
                    <Button onClick={() => onNavigateToStep(EditorForms.WebApplications)}
                            size={'small'}
                            color={"info"}
                            endIcon={<EditOutlined/>}>
                        Edit
                    </Button>
                </Stack>
            }

            <List sx={{padding: 0}} component={Paper} variant={'outlined'}>
                <ReviewListHeader>
                    <ReviewHeaderKey>Web App</ReviewHeaderKey>
                    <ReviewHeaderValue>Details</ReviewHeaderValue>
                </ReviewListHeader>

                {
                    specification?.web_applications?.map((webApp) => {
                        return (
                            <ReviewListItem disableAlternatingColors sx={{alignItems: 'flex-start'}} divider>
                                <ReviewItemKeyWrapper>
                                    <ReviewItemKey size={'small'} label={webApp.name}/>
                                </ReviewItemKeyWrapper>
                                <ReviewItemValue>
                                    <NestedReviewListItem>
                                        <ReviewItemKeyWrapper>Host</ReviewItemKeyWrapper>
                                        <ReviewItemValueOrSkeleton
                                            value={webApp?.host_name}
                                            loading={loading}/>

                                    </NestedReviewListItem>

                                    <NestedReviewListItem>
                                        <ReviewItemKeyWrapper>Path</ReviewItemKeyWrapper>
                                        <ReviewItemValueOrSkeleton
                                            value={webApp?.starting_directory}
                                            loading={loading}/>
                                    </NestedReviewListItem>
                                </ReviewItemValue>
                            </ReviewListItem>
                        );
                    })
                }

                {
                    (specification?.web_applications || []).length == 0 &&
                    <EmptyListItem>
                        {
                            loading ?
                                <Skeleton variant={'rounded'} height={150} width={'100%'}/>
                                :
                                <EmptyListItemText>No Web Applications</EmptyListItemText>
                        }

                    </EmptyListItem>
                }

            </List>


        </Stack>
    )
}

export default NetworkReview;
