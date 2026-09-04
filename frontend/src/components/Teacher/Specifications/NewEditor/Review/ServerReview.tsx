import {EditOutlined} from "@mui/icons-material";
import {Button, List, Paper, Skeleton, Stack, useTheme} from "@mui/material";
import React from "react";
import {SpecificationEdit} from "../../../../../services/Specification/specificationEdit.model";
import ChipListView from "../../../../Common/ChipListView";
import {EditorForms} from "../utils/EditorTypes";
import {ReviewCommonChildrenProps} from "./Review";

import {
    EmptyListItem, EmptyListItemText,
    NestedReviewListItem,
    ReviewHeaderKey,
    ReviewHeaderValue,
    ReviewItemKey, ReviewItemKeyWrapper, ReviewItemValue,
    ReviewListHeader,
    ReviewListItem, ReviewSectionLabel
} from './ReviewCommonStyles';
import ReviewItemValueOrSkeleton from "./ReviewItemValueOrSkeleton";

interface Props extends ReviewCommonChildrenProps {
    specification: SpecificationEdit | undefined,
    loading: boolean;
}


const ServerReview: React.FC<Props> = ({ specification, loading, elevation, onNavigateToStep, includeHeader = true, styles={},}) => {
    const theme = useTheme();

    const serverImage = (image: any) => {
        if (!!image && typeof image == "object") {
            return image.value;
        }
        return image;
    }

    return (
        <Stack sx={styles} component={Paper} elevation={elevation}>
            {
                includeHeader &&
                <Stack sx={{paddingY: theme.spacing(1)}} direction={'row'} alignItems={'center'}
                       justifyContent={'space-between'}>
                    <ReviewSectionLabel variant={'h6'}>Server Review</ReviewSectionLabel>
                    <Button onClick={() => onNavigateToStep(EditorForms.Servers)}
                            size={'small'}
                            color={"info"}
                            endIcon={<EditOutlined/>}>
                        Edit
                    </Button>
                </Stack>
            }

            <List sx={{padding: 0}} component={Paper} variant={'outlined'}>
                <ReviewListHeader>
                    <ReviewHeaderKey>Server</ReviewHeaderKey>
                    <ReviewHeaderValue>Details</ReviewHeaderValue>
                </ReviewListHeader>

                {
                    specification?.servers?.map((server, index) => {
                        return (
                            <ReviewListItem key={index} disableAlternatingColors sx={{alignItems: 'flex-start'}}
                                            divider>
                                <ReviewItemKeyWrapper>
                                    <ReviewItemKey size={'small'} label={server.name}/>
                                </ReviewItemKeyWrapper>
                                <ReviewItemValue>
                                    <NestedReviewListItem>
                                        <ReviewItemKeyWrapper>Labels</ReviewItemKeyWrapper>

                                        <ReviewItemValueOrSkeleton
                                            value={<ChipListView values={server.details.labels?.length > 0 ? server.details.labels : ['No Labels']}/>}
                                            loading={loading}/>
                                    </NestedReviewListItem>

                                    <NestedReviewListItem>
                                        <ReviewItemKeyWrapper>Description</ReviewItemKeyWrapper>
                                        <ReviewItemValueOrSkeleton
                                            value={server.details?.description}
                                            loading={loading}/>

                                    </NestedReviewListItem>

                                    <NestedReviewListItem>
                                        <ReviewItemKeyWrapper>OS</ReviewItemKeyWrapper>
                                        <ReviewItemValueOrSkeleton
                                            value={server.details?.os}
                                            loading={loading}/>
                                    </NestedReviewListItem>

                                    <NestedReviewListItem>
                                        <ReviewItemKeyWrapper>Image</ReviewItemKeyWrapper>
                                        <ReviewItemValueOrSkeleton
                                            value={serverImage(server?.image)}
                                            loading={loading}
                                        />
                                    </NestedReviewListItem>

                                    <NestedReviewListItem>
                                        <ReviewItemKeyWrapper>Machine Type</ReviewItemKeyWrapper>
                                        <ReviewItemValueOrSkeleton
                                            value={server.machine_type}
                                            loading={loading}/>
                                    </NestedReviewListItem>

                                    <NestedReviewListItem>
                                        <ReviewItemKeyWrapper>Community Server</ReviewItemKeyWrapper>
                                        <ReviewItemValueOrSkeleton
                                            value={server.community_server ? 'Yes' : 'No'}
                                            loading={loading}/>
                                    </NestedReviewListItem>

                                    <NestedReviewListItem>
                                        <ReviewItemKeyWrapper>WireGuard Gateway</ReviewItemKeyWrapper>
                                        <ReviewItemValueOrSkeleton
                                            value={server.wireguard_gateway ? 'Yes' : 'No'}
                                            loading={loading}/>
                                    </NestedReviewListItem>

                                    <NestedReviewListItem>
                                        <ReviewItemKeyWrapper>IP Forwarding</ReviewItemKeyWrapper>
                                        <ReviewItemValueOrSkeleton
                                            value={server.can_ip_forward ? 'Enabled' : 'Disabled'}
                                            loading={loading}/>
                                    </NestedReviewListItem>

                                    <NestedReviewListItem>
                                        <ReviewItemKeyWrapper>Network Tags</ReviewItemKeyWrapper>
                                        <ReviewItemValueOrSkeleton
                                            value={<ChipListView values={server.tags?.length ? server.tags : ['No Tags']}/>}
                                            loading={loading}/>
                                    </NestedReviewListItem>

                                    <NestedReviewListItem>
                                        <ReviewItemKeyWrapper>Static Routes</ReviewItemKeyWrapper>
                                        <ReviewItemValueOrSkeleton
                                            value={server.routes?.length ? JSON.stringify(server.routes) : 'None'}
                                            loading={loading}/>
                                    </NestedReviewListItem>

                                    <NestedReviewListItem>
                                        <ReviewItemKeyWrapper>Nics</ReviewItemKeyWrapper>
                                        <ReviewItemValueOrSkeleton
                                            value={JSON.stringify(server.nics)}
                                            loading={loading}/>
                                    </NestedReviewListItem>
                                </ReviewItemValue>
                            </ReviewListItem>
                        );
                    })
                }

                {
                    (specification?.servers || []).length === 0 &&
                    <EmptyListItem>
                        {
                            loading ?
                                <Skeleton variant={'rounded'} height={150} width={'100%'}/>
                                :
                                <EmptyListItemText>No Servers</EmptyListItemText>
                        }
                    </EmptyListItem>
                }

            </List>


        </Stack>
    )
}

export default ServerReview;
