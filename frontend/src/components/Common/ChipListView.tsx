import React from "react";
import Review from "../Teacher/Specifications/NewEditor/Review/Review";
import {Box, Chip, ListItem} from "@mui/material";
import {SummaryFormKeys} from "../Teacher/Specifications/NewEditor/utils/EditorTypes";
import {TeachingConcept} from "../../services/Specification/specificationEdit.model";

interface Props<T> {
    values: T[],
    onRemove?: (value: T) => void,
    renderLabel?: (value: T) => string
}

const ChipListView = <T, >({values, onRemove, renderLabel}: Props<T>): React.ReactElement => {
    const thisRenderLabel = (value: T) => {
        if (renderLabel) {
            return renderLabel(value)
        }

        return value as string;
    }

    return (
        <Box
            sx={{
                display: 'flex',
                justifyContent: 'flex-start',
                flexWrap: 'wrap',
                listStyle: 'none',
                m: 0,
                p: 0
            }}
            component="ul"
        >
            {values?.map((data: T, index: number) => {
                return (
                    <ListItem disableGutters sx={{
                        display: 'inline',
                        width: 'auto',
                        pl: 0,
                        paddingX: .25
                    }} key={index}>
                        <Chip
                            size={'small'}
                            label={thisRenderLabel(data)}
                            onDelete={onRemove ? () => onRemove(data) : undefined}
                        />
                    </ListItem>
                );
            })}
        </Box>
    )
}

export default ChipListView;
