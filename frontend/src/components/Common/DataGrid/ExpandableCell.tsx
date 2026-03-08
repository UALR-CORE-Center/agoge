import {Link, Typography} from "@mui/material";
import {GridRenderCellParams} from "@mui/x-data-grid";
import React from "react";

interface ExpandableCellProps extends GridRenderCellParams {
    variant?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'subtitle1' | 'subtitle2' | 'body1' | 'body2';
    missingText?: string
}

export const ExpandableCell: React.FC<ExpandableCellProps> = (props) => {
    const [expanded, setExpanded] = React.useState(false);

    const missingText = () => {
        if (props.missingText) {
            return props.missingText;
        }
        return "No lab description";
    }
    const renderContent = () => (
        <>
            {expanded ? props.value : props.value.slice(0, 100)}&nbsp;
            {props.value.length > 100 && (
                // eslint-disable-next-line jsx-a11y/anchor-is-valid
                <Link
                    type="button"
                    component="button"
                    sx={{ fontSize: 'inherit' }}
                    onClick={() => setExpanded(!expanded)}
                >
                    {expanded ? 'View Less' : 'View More'}
                </Link>
            )}
        </>
    );

    if (!props.value) {
        return props.variant ? (
            <Typography variant={props.variant}>{missingText()}</Typography>
        ) : (
            <div>{missingText()}</div>
        );
    }

    return props.variant ? (
        <div>
            <Typography variant={props.variant}>
                {renderContent()}
            </Typography>
        </div>
    ) : (
        <div>
            {renderContent()}
        </div>
    );
}