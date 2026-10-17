import {EditOutlined} from "@mui/icons-material";
import {Button, List, Paper, Stack, useTheme} from "@mui/material";
import React from "react";
import {SpecificationEdit} from "../../../../../services/Specification/specificationEdit.model";
import {EditorForms} from "../utils/EditorTypes";
import {ReviewCommonChildrenProps} from "./Review";
import {
    EmptyListItem,
    EmptyListItemText,
    NestedReviewListItem,
    ReviewHeaderKey,
    ReviewHeaderValue,
    ReviewItemKey,
    ReviewItemKeyWrapper,
    ReviewItemValue,
    ReviewListHeader,
    ReviewListItem,
    ReviewSectionLabel
} from "./ReviewCommonStyles";
import ReviewItemValueOrSkeleton from "./ReviewItemValueOrSkeleton";

interface Props extends ReviewCommonChildrenProps {
    specification: SpecificationEdit | undefined;
    loading: boolean;
}

const CtfReview: React.FC<Props> = ({specification, loading, elevation, onNavigateToStep, styles = {}}) => {
    const theme = useTheme();
    const ctf = specification?.ctf;

    return (
        <Stack sx={styles} component={Paper} elevation={elevation}>
            <Stack sx={{paddingY: theme.spacing(1)}} direction={'row'} alignItems={'center'}
                   justifyContent={'space-between'} flexWrap={'wrap'} gap={1}>
                <ReviewSectionLabel variant={'h6'}>CTF Review{ctf?.name ? `: ${ctf.name}` : ''}</ReviewSectionLabel>
                <Button onClick={() => onNavigateToStep(EditorForms.Ctf)} size={'small'} color={"info"}
                        endIcon={<EditOutlined/>}>
                    Edit
                </Button>
            </Stack>

            <List sx={{padding: 0}} component={Paper} variant={'outlined'}>
                <ReviewListHeader>
                    <ReviewHeaderKey>Flag</ReviewHeaderKey>
                    <ReviewHeaderValue>Details</ReviewHeaderValue>
                </ReviewListHeader>

                {ctf?.flags.map((flag) => (
                    <ReviewListItem key={flag.id} disableAlternatingColors sx={{alignItems: 'flex-start'}} divider>
                        <ReviewItemKeyWrapper>
                            <ReviewItemKey size={'small'} label={flag.id}/>
                        </ReviewItemKeyWrapper>
                        <ReviewItemValue>
                            <NestedReviewListItem>
                                <ReviewItemKeyWrapper>Server</ReviewItemKeyWrapper>
                                <ReviewItemValueOrSkeleton value={`${flag.server} (slot ${flag.slot})`} loading={loading}/>
                            </NestedReviewListItem>
                            <NestedReviewListItem>
                                <ReviewItemKeyWrapper>Location</ReviewItemKeyWrapper>
                                <ReviewItemValueOrSkeleton value={`${flag.location_type}: ${flag.path}`} loading={loading}/>
                            </NestedReviewListItem>
                            <NestedReviewListItem>
                                <ReviewItemKeyWrapper>Points</ReviewItemKeyWrapper>
                                <ReviewItemValueOrSkeleton
                                    value={`${flag.points}${flag.decoy ? ' (decoy)' : ''}`}
                                    loading={loading}/>
                            </NestedReviewListItem>
                        </ReviewItemValue>
                    </ReviewListItem>
                ))}

                {(ctf?.flags || []).length === 0 && (
                    <EmptyListItem>
                        <EmptyListItemText>No flags. A CTF template needs at least one.</EmptyListItemText>
                    </EmptyListItem>
                )}
            </List>
        </Stack>
    );
};

export default CtfReview;
