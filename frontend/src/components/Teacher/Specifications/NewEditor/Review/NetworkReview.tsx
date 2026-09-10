import React from "react";
import {Box, Button, List, ListItem, ListItemText, Paper, Skeleton, Stack, Typography, useTheme} from "@mui/material";
import {SpecificationEdit} from "../../../../../services/Specification/specificationEdit.model";
import {ReviewCommonChildrenProps} from "./Review";
import {EditorForms} from "../utils/EditorTypes";
import {EditOutlined} from "@mui/icons-material";
import {
    EmptyListItem, EmptyListItemText,
    NestedReviewListItem,
    ReviewHeaderKey,
    ReviewHeaderValue,
    ReviewItemKey,
    ReviewItemKeyWrapper,
    ReviewItemValue,
    ReviewListHeader,
    ReviewListItem,
    ReviewSectionLabel,
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
                    <ReviewSectionLabel variant={'h6'}>Network Review</ReviewSectionLabel>
                    <Button onClick={() => onNavigateToStep(EditorForms.Networks)}
                            size={'small'}
                            color={"info"}
                            endIcon={<EditOutlined/>}>
                        Edit
                    </Button>
                </Stack>
            }



            <List sx={{padding: 0}} component={Paper} variant={'outlined'}>
                <ReviewListHeader>
                    <ReviewHeaderKey>Network</ReviewHeaderKey>
                    <ReviewHeaderValue>Details</ReviewHeaderValue>
                </ReviewListHeader>

                {
                    specification?.networks?.map((network, idx) => {
                        const subnet = network.subnets?.length ? network.subnets[0] : null;
                        return (
                            <ReviewListItem key={idx} disableAlternatingColors sx={{alignItems: 'flex-start'}} divider>
                                <ReviewItemKeyWrapper>
                                    <ReviewItemKey size={'small'} label={network.name}/>
                                </ReviewItemKeyWrapper>
                                <ReviewItemValue>
                                    <NestedReviewListItem>
                                        <ReviewItemKeyWrapper>Name</ReviewItemKeyWrapper>

                                        <ReviewItemValueOrSkeleton
                                            value={subnet?.name}
                                            loading={loading}/>

                                    </NestedReviewListItem>

                                    <NestedReviewListItem>
                                        <ReviewItemKeyWrapper>Subnet</ReviewItemKeyWrapper>
                                        <ReviewItemValueOrSkeleton
                                            value={subnet?.ip_subnet}
                                            loading={loading}/>
                                    </NestedReviewListItem>
                                </ReviewItemValue>
                            </ReviewListItem>
                        );
                    })
                }

                {
                    (specification?.networks || []).length == 0 &&
                    <EmptyListItem>
                        {
                            loading ?
                                <Skeleton variant={'rounded'} height={150} width={'100%'}/>
                                :
                                <EmptyListItemText>No Networks</EmptyListItemText>
                        }
                    </EmptyListItem>
                }

            </List>

            <ReviewSectionLabel sx={{paddingY: theme.spacing(1), marginTop: theme.spacing(1)}} variant={'h6'}>
                Static Routes
            </ReviewSectionLabel>

            <List sx={{padding: 0}} component={Paper} variant={'outlined'}>
                <ReviewListHeader>
                    <ReviewHeaderKey>Route</ReviewHeaderKey>
                    <ReviewHeaderValue>Details</ReviewHeaderValue>
                </ReviewListHeader>

                {specification?.routes?.map((route, idx) => (
                    <ReviewListItem
                        key={`${route.name}-${idx}`}
                        disableAlternatingColors
                        sx={{alignItems: 'flex-start'}}
                        divider
                    >
                        <ReviewItemKeyWrapper>
                            <ReviewItemKey size={'small'} label={route.name}/>
                        </ReviewItemKeyWrapper>
                        <ReviewItemValue>
                            <NestedReviewListItem>
                                <ReviewItemKeyWrapper>Destination</ReviewItemKeyWrapper>
                                <ReviewItemValueOrSkeleton
                                    value={route.dest_range}
                                    loading={loading}/>
                            </NestedReviewListItem>

                            <NestedReviewListItem>
                                <ReviewItemKeyWrapper>Network</ReviewItemKeyWrapper>
                                <ReviewItemValueOrSkeleton
                                    value={route.network}
                                    loading={loading}/>
                            </NestedReviewListItem>

                            <NestedReviewListItem>
                                <ReviewItemKeyWrapper>Next Hop</ReviewItemKeyWrapper>
                                <ReviewItemValueOrSkeleton
                                    value={route.next_hop_instance}
                                    loading={loading}/>
                            </NestedReviewListItem>

                            <NestedReviewListItem>
                                <ReviewItemKeyWrapper>Priority</ReviewItemKeyWrapper>
                                <ReviewItemValueOrSkeleton
                                    value={String(route.priority ?? 1000)}
                                    loading={loading}/>
                            </NestedReviewListItem>

                            <NestedReviewListItem>
                                <ReviewItemKeyWrapper>Applies To</ReviewItemKeyWrapper>
                                <ReviewItemValueOrSkeleton
                                    value={
                                        route.tags?.length
                                            ? <ChipListView values={route.tags}/>
                                            : 'All instances'
                                    }
                                    loading={loading}/>
                            </NestedReviewListItem>

                            {route.description && (
                                <NestedReviewListItem>
                                    <ReviewItemKeyWrapper>Description</ReviewItemKeyWrapper>
                                    <ReviewItemValueOrSkeleton
                                        value={route.description}
                                        loading={loading}/>
                                </NestedReviewListItem>
                            )}
                        </ReviewItemValue>
                    </ReviewListItem>
                ))}

                {(specification?.routes || []).length === 0 && (
                    <EmptyListItem>
                        {loading
                            ? <Skeleton variant={'rounded'} height={100} width={'100%'}/>
                            : <EmptyListItemText>No Static Routes</EmptyListItemText>
                        }
                    </EmptyListItem>
                )}
            </List>


        </Stack>
    )
}

export default NetworkReview;
