import React from "react";
import ChipListView from "../../../../Common/ChipListView";
import {ReviewItemValue} from "./ReviewCommonStyles";
import {Skeleton, useTheme} from "@mui/material";
import Review from "./Review";
import {useClipboard} from "../../../../../hooks/useClipboard";


interface Props {
    value: string | React.ReactNode | undefined;
    loading: boolean;
}

const ReviewItemValueOrSkeleton: React.FC<Props> = ({value, loading}) => {

    const render = () => {
        if (loading) {
            return (
                <Skeleton variant="rectangular" width={'100%'} height={30}/>
            )
        } else if (value) {
            return value;
        } else {
            return 'N/A'
        }
    }

    return (
        <ReviewItemValue>
            {render()}
        </ReviewItemValue>
    )

}


export default ReviewItemValueOrSkeleton;
