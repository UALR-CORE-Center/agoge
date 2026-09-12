import {Close, EditOutlined} from "@mui/icons-material";
import {Button, Dialog, DialogContent, DialogTitle, IconButton, List, Paper, Stack, useTheme} from "@mui/material";
import DialogActions from "@mui/material/DialogActions";
import React from "react";
import {useNavigate} from "react-router-dom";
import {URL_TEACHER_SERVERS_EDITOR} from "../../../../router/urls";
import {AgogeImage} from "../../../../services/Server/image.model";
import ChipListView from "../../../Common/ChipListView";
import ReviewItemValueOrSkeleton from "../../Specifications/NewEditor/Review/ReviewItemValueOrSkeleton";
import {
    ImageListItem,
    NestedListItem,
    ItemValue,
    SectionLabel,
    ItemKeyWrapper
} from "./DialogFieldStyles";

interface ImageDetails {
    open: boolean;
    image: AgogeImage | null;
    onClose: () => void;
    loading: boolean;
    onEdit?: (image: AgogeImage) => void;
}

export const ImageDetailsDialog: React.FC<ImageDetails> = (props) => {
    const theme = useTheme();
    const navigate = useNavigate();
    const image = props.image;
    const loading = props.loading;
    const operatingSystem = image?.base_family ? image.base_family : image?.os;

    const handleOnClose = () => {
        if (props.onClose) {
            props.onClose();
        }
    }

    const onNavigateToEdit = () => {
        if (image) {
            if (props.onEdit) {
                props.onEdit(image);
                return;
            }
            const href = `${URL_TEACHER_SERVERS_EDITOR}/${image.name}`
            navigate(href);
        }
    }

    return (
        <>
            {
                image && (
                    <Dialog
                        open={props.open}
                        onClose={handleOnClose}
                        maxWidth={"lg"}
                        sx={{minWidth: "60vw"}}
                    >
                        <DialogTitle justifyContent={"center"}>
                            <Stack direction={'row'} alignItems={'center'} justifyContent={'space-between'}>
                                {`${image.name} details`}
                                <IconButton
                                    onClick={handleOnClose}
                                    aria-label={"close image details"}
                                    color={"error"}
                                    title={"Close image details"}

                                >
                                    <Close />
                                </IconButton>
                            </Stack>
                        </DialogTitle>
                        <DialogContent>
                            <Stack sx={{padding:2}} component={Paper} elevation={1}>
                                <Stack sx={{paddingY: theme.spacing(1)}} direction={'row'} alignItems={'center'}
                                       justifyContent={'space-between'}>
                                    <SectionLabel variant={'h6'}>Details</SectionLabel>
                                    <Button
                                        onClick={() => onNavigateToEdit()}
                                        size={'small'}
                                        color={"info"}
                                        endIcon={<EditOutlined/>}
                                    >
                                        {image.is_shared ? 'Copy and edit' : 'Edit'}
                                    </Button>
                                </Stack>

                                <List  sx={{padding: 0}} component={Paper} variant={'outlined'}>
                                    <ImageListItem disableAlternatingColors sx={{alignItems: 'flex-start'}} divider>
                                        <ItemValue>
                                            <NestedListItem>
                                                <ItemKeyWrapper>Source</ItemKeyWrapper>
                                                <ReviewItemValueOrSkeleton
                                                    value={`${image.is_shared ? 'Shared' : 'Local'}${image.source_project ? ` (${image.source_project})` : ''}`}
                                                    loading={loading}
                                                />
                                            </NestedListItem>
                                            <NestedListItem>
                                                <ItemKeyWrapper>Description</ItemKeyWrapper>
                                                <ReviewItemValueOrSkeleton
                                                    value={image.description}
                                                    loading={loading}
                                                />
                                            </NestedListItem>

                                            <NestedListItem>
                                                <ItemKeyWrapper>Operating System (OS)</ItemKeyWrapper>
                                                <ReviewItemValueOrSkeleton
                                                    value={operatingSystem}
                                                    loading={loading}
                                                />
                                            </NestedListItem>

                                            <NestedListItem>
                                                <ItemKeyWrapper>Image</ItemKeyWrapper>
                                                <ReviewItemValueOrSkeleton
                                                    value={image.image}
                                                    loading={loading}
                                                />
                                            </NestedListItem>

                                            <NestedListItem>
                                                <ItemKeyWrapper>Machine Type</ItemKeyWrapper>
                                                <ReviewItemValueOrSkeleton
                                                    value={image.machine_type}
                                                    loading={loading}
                                                />
                                            </NestedListItem>

                                            <NestedListItem>
                                                <ItemKeyWrapper>Human Interaction</ItemKeyWrapper>
                                                {/* TODO: Convert this to a list of connections */}
                                                <ReviewItemValueOrSkeleton
                                                    value={JSON.stringify(image.human_interaction)}
                                                    loading={loading}
                                                />
                                            </NestedListItem>

                                            <NestedListItem>
                                                <ItemKeyWrapper>
                                                    Labels
                                                </ItemKeyWrapper>
                                                <ReviewItemValueOrSkeleton
                                                    value={<ChipListView values={image.labels || []} />}
                                                    loading={loading}
                                                />
                                            </NestedListItem>
                                        </ItemValue>
                                    </ImageListItem>
                                </List>
                            </Stack>
                        </DialogContent>
                        <DialogActions>
                            <Button onClick={handleOnClose}>Close</Button>
                        </DialogActions>
                    </Dialog>
                )
            }
        </>
    );
}
