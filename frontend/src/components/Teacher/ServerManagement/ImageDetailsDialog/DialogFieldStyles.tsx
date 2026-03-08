import {ListItem, ListItemText, Stack, styled, Theme, Typography} from "@mui/material";
import MuiChip from "@mui/material/Chip";

export const HeaderKey = styled(ListItemText)(({theme}: {
    theme: Theme
}) => ({
    width: '30%',
    borderRight: `1px solid ${theme.palette.divider}`,
    paddingLeft: theme.spacing(1),
    '& .MuiTypography-root': {
        fontSize: theme.typography.subtitle2.fontSize,
        fontWeight: 600,
    },
}));

export const HeaderValue = styled(ListItemText)(({theme}: {
    theme: Theme
}) => ({
    width: '70%',
    paddingLeft: theme.spacing(1),
    '& .MuiTypography-root': {
        fontSize: theme.typography.subtitle2.fontSize,
        fontWeight: 600,
    },
}));

export const ListHeader = styled(ListItem)({
    background: 'black',
    padding: `1px 0px`
})


interface CustomProps {
    disableAlternatingColors?: boolean;
}


export const EmptyListItem = styled(ListItem, {
    shouldForwardProp: (prop) => prop !== 'disableAlternatingColors',
})<CustomProps>(({ theme, disableAlternatingColors }) => ({
    textAlign: 'center'
}));

export const EmptyListItemText = styled(ListItemText, {
    shouldForwardProp: (prop) => prop !== 'disableAlternatingColors',
})<CustomProps>(({ theme, disableAlternatingColors }) => ({
    padding: theme.spacing(2),
    '& .MuiTypography-root': {
        fontSize: theme.typography.body2.fontSize,
        color: theme.palette.text.secondary
    },
}));

export const ImageListItem = styled(ListItem, {
    shouldForwardProp: (prop) => prop !== 'disableAlternatingColors',
})<CustomProps>(({ theme, disableAlternatingColors }) => ({
    display: 'flex',
    alignItems: 'stretch',
    padding: '0px 0',
    '&:nth-of-type(odd)': {
        backgroundColor: !disableAlternatingColors ? theme.palette.action.hover : undefined,
    },
    '&:nth-of-type(even)': {
        backgroundColor: !disableAlternatingColors ? theme.palette.background.default : undefined,
    },
}));

export const NestedListItem = styled(Stack, {
    shouldForwardProp: (prop) => prop !== 'disableAlternatingColors',
})<CustomProps>(({ theme, disableAlternatingColors }) => ({
    display: 'flex',
    flexDirection: 'row',
    alignItems: 'stretch',
    padding: '3px 0',
    '&:nth-of-type(odd)': {
        backgroundColor: !disableAlternatingColors ? theme.palette.action.hover : undefined,
    },
    '&:nth-of-type(even)': {
        backgroundColor: !disableAlternatingColors ? theme.palette.background.default : undefined,
    },
    border: '1px solid ' + theme.palette.divider
}));


export const ItemKey = styled(MuiChip)<{ theme?: Theme }>(({theme}) => ({
    fontWeight: 600,
    background: theme.palette.success.main
}));


export const SectionLabel = styled(Typography)<{ theme?: Theme }>(({theme}) => ({
    fontSize: '1rem',
    fontWeight: 600,
}));


export const ItemKeyWrapper = styled(ListItemText)(({theme}: {
    theme: Theme
}) => ({
    width: '30%',
    paddingLeft: theme.spacing(1),
    display: 'flex',
    alignItems: 'center',
}));



export const ItemValue = styled(ListItemText)(({theme}: {
    theme: Theme
}) => ({
    width: '70%',
    '& .MuiTypography-root': {
        fontSize: theme.typography.body2.fontSize,
        wordBreak: 'break-word',
        overflowWrap: 'break-word',
        whiteSpace: 'normal'
    },
    margin: 0,
}));

