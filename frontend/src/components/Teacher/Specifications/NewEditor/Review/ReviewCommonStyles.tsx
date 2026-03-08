import {ListItem, ListItemText, Stack, styled, Theme, Typography} from "@mui/material";
import MuiChip from "@mui/material/Chip";

export const ReviewHeaderKey = styled(ListItemText)(({theme}: {
    theme: Theme
}) => ({
    width: '30%',
    borderRight: `1px solid ${theme.palette.divider}`,
    paddingLeft: theme.spacing(1),
    '& .MuiTypography-root': {
        fontSize: theme.typography.subtitle2.fontSize,
        fontWeight: 600,
        color: theme.palette.common.white
    },
}));

export const ReviewHeaderValue = styled(ListItemText)(({theme}: {
    theme: Theme
}) => ({
    width: '70%',
    paddingLeft: theme.spacing(1),
    '& .MuiTypography-root': {
        fontSize: theme.typography.subtitle2.fontSize,
        fontWeight: 600,
    },
}));

export const ReviewListHeader = styled(ListItem)({
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

export const ReviewListItem = styled(ListItem, {
    shouldForwardProp: (prop) => prop !== 'disableAlternatingColors',
})<CustomProps>(({ theme, disableAlternatingColors }) => ({
    display: 'flex',
    alignItems: 'stretch',
    padding: '3px 0',
    '&:nth-of-type(odd)': {
        backgroundColor: !disableAlternatingColors ? theme.palette.action.hover : undefined,
    },
    '&:nth-of-type(even)': {
        backgroundColor: !disableAlternatingColors ? theme.palette.background.default : undefined,
    },
}));

export const NestedReviewListItem = styled(Stack, {
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


export const ReviewItemKey = styled(MuiChip)<{ theme?: Theme }>(({theme}) => ({
    fontWeight: 600,
    background: '#1565aa',
    color: theme.palette.common.white
}));


export const ReviewSectionLabel = styled(Typography)<{ theme?: Theme }>(({theme}) => ({
    fontSize: '1rem',
    fontWeight: 600,
}));


export const ReviewItemKeyWrapper = styled(ListItemText)(({theme}: {
    theme: Theme
}) => ({
    width: '30%',
    paddingLeft: theme.spacing(1),
    display: 'flex',
    alignItems: 'center',
}));



export const ReviewItemValue = styled(ListItemText)(({theme}: {
    theme: Theme
}) => ({
    width: '70%',
    paddingLeft: theme.spacing(1),
    paddingRight: theme.spacing(1),
    borderLeft: `1px solid ${theme.palette.divider}`,
    '& .MuiTypography-root': {
        fontSize: theme.typography.body2.fontSize,
        wordBreak: 'break-word',
        overflowWrap: 'break-word',
        whiteSpace: 'normal'
    },
}));

