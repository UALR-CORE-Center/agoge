import Grid from '@mui/material/Grid2';
import React from "react";
import {GridItem} from "./GridItem";

interface ResponsiveGridProps {
    items: React.ReactNode[];
    itemPadding?: number;
}


export const ResponsiveGrid: React.FC<ResponsiveGridProps> = (props) => {
    return (
        <>
            <Grid
                container
                spacing={{ xs: 2, md: 3 }}
                columns={{ xs: 4, sm: 8, md: 12 }}
            >
                {props.items.map((item, index) => (
                    <Grid key={index} size={{ xs: 2, sm: 4, md: 4 }}>
                        <GridItem padding={props.itemPadding}>{item}</GridItem>
                    </Grid>
                ))}
            </Grid>
        </>
    )
}