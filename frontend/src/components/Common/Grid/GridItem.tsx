import {Paper, styled} from "@mui/material";

interface GridItemProps {
    padding?: number;
}


export const GridItem = styled(Paper)<GridItemProps>(({ theme, padding }) => ({
    ...theme.typography.body2,
    padding: theme.spacing(padding ?? 1),
    textAlign: 'center',
    color: theme.palette.text.secondary,
}));