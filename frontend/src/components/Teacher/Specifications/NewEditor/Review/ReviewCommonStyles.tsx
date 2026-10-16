import {ListItem, ListItemText, Stack, styled, Theme, Typography} from "@mui/material";
import MuiChip from "@mui/material/Chip";

/*
 * These components draw two-column key/value "tables" out of List markup.
 *
 * Columns stay fluid (30% key / 70% value) for as long as the row has room for
 * both. Once the row itself is narrower than a setpoint, the key stacks above its
 * value instead of pushing content past the right edge. The setpoint is a
 * container query on the row, not a viewport media query, because these lists
 * render inside dialogs, the editor card, and other rows' value cells, where the
 * available width has little to do with the screen width.
 */

// Rows narrower than these can no longer fit a key and a value side by side.
const ROW_STACK_BELOW = 560;
const NESTED_ROW_STACK_BELOW = 360;

const ROW_CONTAINER = 'review-row';
const NESTED_ROW_CONTAINER = 'review-nested-row';

const KEY_COLUMN = '30%';

// Shared by the header and body rows so their columns line up.
const fluidColumns = {
    flexWrap: 'wrap' as const,
    '& > .MuiListItemText-root': {
        // Without minWidth: 0 a flex item can't shrink below its longest word,
        // which is what pushed long names and URLs out of their column.
        minWidth: 0,
    },
    '& > .MuiListItemText-root:first-of-type': {
        flex: `0 0 ${KEY_COLUMN}`,
    },
    '& > .MuiListItemText-root:not(:first-of-type)': {
        flex: '1 1 0',
    },
};

const stackedColumns = (theme: Theme) => ({
    '& > .MuiListItemText-root, & > .MuiListItemText-root:first-of-type, & > .MuiListItemText-root:not(:first-of-type)': {
        flexBasis: '100%',
        borderLeft: 'none',
        borderRight: 'none',
    },
    // Stacked, a plain-text key reads like its value unless styled as a label.
    '& > .MuiListItemText-root:first-of-type > .MuiTypography-root': {
        fontWeight: 600,
        color: theme.palette.text.secondary,
    },
});

export const ReviewHeaderKey = styled(ListItemText)(({theme}: {
    theme: Theme
}) => ({
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
    paddingLeft: theme.spacing(1),
    '& .MuiTypography-root': {
        fontSize: theme.typography.subtitle2.fontSize,
        fontWeight: 600,
    },
}));

export const ReviewListHeader = styled(ListItem)(({theme}: {
    theme: Theme
}) => ({
    background: 'black',
    padding: `1px 0px`,
    containerType: 'inline-size',
    containerName: ROW_CONTAINER,
    ...fluidColumns,
    // Once rows stack, "Key | Value" column titles no longer sit over anything,
    // and every row already labels itself with its key chip.
    [theme.containerQueries(ROW_CONTAINER).down(ROW_STACK_BELOW)]: {
        padding: 0,
        '& > .MuiListItemText-root': {
            display: 'none',
        },
    },
}));


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
    containerType: 'inline-size',
    containerName: ROW_CONTAINER,
    ...fluidColumns,
    '&:nth-of-type(odd)': {
        backgroundColor: !disableAlternatingColors ? theme.palette.action.hover : undefined,
    },
    '&:nth-of-type(even)': {
        backgroundColor: !disableAlternatingColors ? theme.palette.background.default : undefined,
    },
    [theme.containerQueries(ROW_CONTAINER).down(ROW_STACK_BELOW)]: stackedColumns(theme),
}));

export const NestedReviewListItem = styled(Stack, {
    shouldForwardProp: (prop) => prop !== 'disableAlternatingColors',
})<CustomProps>(({ theme, disableAlternatingColors }) => ({
    display: 'flex',
    flexDirection: 'row',
    alignItems: 'stretch',
    padding: '3px 0',
    containerType: 'inline-size',
    containerName: NESTED_ROW_CONTAINER,
    ...fluidColumns,
    '&:nth-of-type(odd)': {
        backgroundColor: !disableAlternatingColors ? theme.palette.action.hover : undefined,
    },
    '&:nth-of-type(even)': {
        backgroundColor: !disableAlternatingColors ? theme.palette.background.default : undefined,
    },
    border: '1px solid ' + theme.palette.divider,
    [theme.containerQueries(NESTED_ROW_CONTAINER).down(NESTED_ROW_STACK_BELOW)]: stackedColumns(theme),
}));


export const ReviewItemKey = styled(MuiChip)<{ theme?: Theme }>(({theme}) => ({
    fontWeight: 600,
    background: '#1565aa',
    color: theme.palette.common.white,
    // Long names (servers, networks, routes) wrap inside the chip rather than
    // overflowing the key column.
    maxWidth: '100%',
    height: 'auto',
    minHeight: 24,
    '& .MuiChip-label': {
        whiteSpace: 'normal',
        overflowWrap: 'anywhere',
        paddingTop: 2,
        paddingBottom: 2,
    },
}));


export const ReviewSectionLabel = styled(Typography)<{ theme?: Theme }>(({theme}) => ({
    fontSize: '1rem',
    fontWeight: 600,
}));


export const ReviewItemKeyWrapper = styled(ListItemText)(({theme}: {
    theme: Theme
}) => ({
    paddingLeft: theme.spacing(1),
    paddingRight: theme.spacing(1),
    display: 'flex',
    alignItems: 'center',
    // ListItemText wraps the key in a Typography; let it shrink so the chip's
    // maxWidth resolves against the column instead of the chip's own width.
    '& > .MuiTypography-root': {
        minWidth: 0,
        maxWidth: '100%',
        overflowWrap: 'anywhere',
    },
}));



export const ReviewItemValue = styled(ListItemText)(({theme}: {
    theme: Theme
}) => ({
    paddingLeft: theme.spacing(1),
    paddingRight: theme.spacing(1),
    borderLeft: `1px solid ${theme.palette.divider}`,
    '& .MuiTypography-root': {
        fontSize: theme.typography.body2.fontSize,
        wordBreak: 'break-word',
        overflowWrap: 'anywhere',
        whiteSpace: 'normal'
    },
}));
