import {Close} from "@mui/icons-material";
import {Dialog, DialogContent, DialogTitle, IconButton, List, Paper, Stack} from "@mui/material";
import React, {useState} from "react";
import {Specification} from "../../../../services/Specification/specification.model";
import {SpecificationEdit, TeachingConcept} from "../../../../services/Specification/specificationEdit.model";
import ChipListView from "../../../Common/ChipListView";
import NetworkReview from "../NewEditor/Review/NetworkReview";
import {
    ReviewHeaderKey,
    ReviewHeaderValue,
    ReviewItemKey,
    ReviewItemKeyWrapper,
    ReviewListHeader,
    ReviewListItem
} from "../NewEditor/Review/ReviewCommonStyles";
import ReviewItemValueOrSkeleton from "../NewEditor/Review/ReviewItemValueOrSkeleton";
import ServerReview from "../NewEditor/Review/ServerReview";

interface Props {
    specification: Specification
}

export default function CatalogDetailsDialog(props: Props) {
    const {specification} = props;
    const [open, setOpen] = useState(true);

    const catalogTags = (): TeachingConcept[] => {
        if (!specification.summary.tags || specification.summary.tags?.length == 0) {
            return [{id: '-1', name: 'No Tags'}]
        }

        return specification.summary.tags;
    }


    const elevation = 8;
    const loading = specification == undefined;
    return (
        <Dialog
            open={open}
            onClose={() => setOpen(false)}
            maxWidth={"md"}
            fullWidth
        >
            <DialogTitle justifyContent={"center"}>
                <Stack direction={'row'} alignItems={'center'} justifyContent={'space-between'}>
                    {`${specification.summary.name} details`}
                    <IconButton
                        onClick={() => setOpen(false)}
                        aria-label={"close catalog details"}
                        color={"error"}
                        title={"Close catalog details"}

                    >
                        <Close />
                    </IconButton>
                </Stack>
            </DialogTitle>
            <DialogContent sx={{maxHeight: "80vh"}}>
                <Stack sx={{padding:2}} gap={1} component={Paper} elevation={1}>
                    {/*<List  sx={{padding: 0}} component={Paper} variant={'outlined'}>*/}

                    <List sx={{padding: 0}} component={Paper} variant={'outlined'}>
                        <ReviewListHeader>
                            <ReviewHeaderKey>Summary</ReviewHeaderKey>
                            <ReviewHeaderValue>Values</ReviewHeaderValue>
                        </ReviewListHeader>

                        <ReviewListItem divider>
                            <ReviewItemKeyWrapper>
                                <ReviewItemKey size={'small'} label={"Name"}/>
                            </ReviewItemKeyWrapper>
                            <ReviewItemValueOrSkeleton value={specification?.summary?.description} loading={loading}/>
                        </ReviewListItem>

                        <ReviewListItem divider>
                            <ReviewItemKeyWrapper>
                                <ReviewItemKey size={'small'} label={"Tags"}/>
                            </ReviewItemKeyWrapper>
                            <ReviewItemValueOrSkeleton
                                value={<ChipListView renderLabel={(tag) => tag.name} values={catalogTags()}/>}
                                loading={loading}/>
                        </ReviewListItem>
                    </List>


                    <NetworkReview elevation={elevation} loading={loading}
                                   includeHeader={false}
                                   specification={specification as unknown as SpecificationEdit} onNavigateToStep={() => {}}/>

                    <ServerReview elevation={elevation} loading={loading} specification={specification as unknown as SpecificationEdit}
                                  includeHeader={false}
                                  onNavigateToStep={() => {}}/>

                </Stack>
            </DialogContent>
        </Dialog>
    );
};