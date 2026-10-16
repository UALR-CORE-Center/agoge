import {ListItem, ListItemText, Stack, styled, Theme, Typography} from "@mui/material";
import MuiChip from "@mui/material/Chip";

// Detail rows keep fluid 30/70 columns until the row itself is too narrow for
// both, then stack the key above its value. This is a container query on the
// row rather than a viewport breakpoint because the rows live in a dialog whose
// width is not the screen width. Mirrors ReviewCommonStyles.
const ROW_STACK_BELOW = 360;
const ROW_CONTAINER = 'detail-row';

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
    border: '1px solid ' + theme.palette.divider,
    containerType: 'inline-size',
    containerName: ROW_CONTAINER,
    flexWrap: 'wrap',
    '& > .MuiListItemText-root': {
        // Lets columns shrink below their longest word (image paths, JSON).
        minWidth: 0,
    },
    '& > .MuiListItemText-root:first-of-type': {
        flex: '0 0 30%',
    },
    '& > .MuiListItemText-root:not(:first-of-type)': {
        flex: '1 1 0',
    },
    [theme.containerQueries(ROW_CONTAINER).down(ROW_STACK_BELOW)]: {
        '& > .MuiListItemText-root, & > .MuiListItemText-root:first-of-type, & > .MuiListItemText-root:not(:first-of-type)': {
            flexBasis: '100%',
            borderLeft: 'none',
        },
        '& > .MuiListItemText-root:first-of-type > .MuiTypography-root': {
            fontWeight: 600,
            color: theme.palette.text.secondary,
        },
    },
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
    paddingLeft: theme.spacing(1),
    paddingRight: theme.spacing(1),
    display: 'flex',
    alignItems: 'center',
}));



export const ItemValue = styled(ListItemText)(({theme}: {
    theme: Theme
}) => ({
    minWidth: 0,
    '& .MuiTypography-root': {
        fontSize: theme.typography.body2.fontSize,
        wordBreak: 'break-word',
        overflowWrap: 'anywhere',
        whiteSpace: 'normal'
    },
    margin: 0,
}));

