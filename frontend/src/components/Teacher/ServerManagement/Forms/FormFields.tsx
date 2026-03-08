import {
    Checkbox,
    FormControl,
    FormControlLabel, FormHelperText,
    ListItem,
    ListItemText,
    Paper,
    Stack,
    styled,
    TextField,
    Theme,
    Typography
} from "@mui/material";
import {lighten, SxProps} from "@mui/system";
import React from "react";
import {HumanInteraction, ServerMachineTypes} from "../../../../services/Specification/specificationEdit.model";
import {FormType, IFormField, IFormFieldMeta} from "../../../../types/Form";


export interface DiskSizeProps {
    error: string | null;
    value: number;
    min: number;
    max: number;
}

export interface MachineTypeStates {
    selectedMachineTypeRow: ServerMachineTypes | null;
    selectedMachineTypeError: boolean;
    machineType: string;
}

export enum IFormKeys {
    DESCRIPTION,
    TAGS,
    MACHINE_TYPE,
    HUMAN_INTERACTION,
    DISK_SIZE,
    IMAGE,
    NAME,
}

export interface IServerForm {
    [IFormKeys.DESCRIPTION]: string;
    [IFormKeys.TAGS]: string[];
    [IFormKeys.MACHINE_TYPE]: string;
    [IFormKeys.HUMAN_INTERACTION]: HumanInteraction[];
    [IFormKeys.DISK_SIZE]: number;
}

export interface ICreateServerForm extends IServerForm {
    [IFormKeys.IMAGE]: string;
    [IFormKeys.NAME]: string;
}


export enum IHumanInteractionFormKeys {
    DISPLAY,
    PASSWORD,
    PROTOCOL,
    SECURITY_MODE,
    SSH_KEY,
    USERNAME,
}

export interface IHumanInteractionForm {
    [IHumanInteractionFormKeys.DISPLAY]: IFormField;
    [IHumanInteractionFormKeys.PASSWORD]: IFormField;
    [IHumanInteractionFormKeys.PROTOCOL]: IFormField;
    [IHumanInteractionFormKeys.SECURITY_MODE]: IFormField;
    [IHumanInteractionFormKeys.SSH_KEY]: IFormField;
    [IHumanInteractionFormKeys.USERNAME]: IFormField;
}

interface FormRowProps {
    gap?: number;
    theme?: any;

    alignItems?: string;
}

export const StyledFormFieldLabel = styled(Typography)(({theme}) => ({
    fontSize: '.95em',
    fontWeight: 'bold'
}));

export const StyledFormTextField = styled(TextField)(({theme}) => ({
    width: '100%',
    required: true,
    input: {
        background: lighten(theme.palette.background.paper, .05)
    },
    p: {
        color: `${theme.palette.text.secondary} !important`
    }
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

export const FormGroup = styled(Stack, {
    shouldForwardProp: (prop) => prop !== 'theme' && prop !== 'gap',
})<FormRowProps>(({theme, gap}) => ({
    gap: theme.spacing(gap || 1),
}));


export const FormGroupOutline = styled(Paper, {
    shouldForwardProp: (prop) => prop !== 'theme' && prop !== 'showOverlay',
})<{ theme?: Theme, showOverlay?: boolean }>(({theme, showOverlay}) => ({
    background: 'transparent',
    border: '2px solid ' + theme.palette.divider,
    padding: theme.spacing(3),
    opacity: showOverlay ? .25 : 1,
    width: '100%'
}));

export const FormFields = styled(Stack, {
    shouldForwardProp: (prop) => prop !== 'theme' && prop !== 'gap',
})<FormRowProps>(({theme, gap}) => ({
    gap: theme.spacing(gap || 3),
    margin: `${theme.spacing(2)} 0`
}));

interface IFormCheckBoxProps {
    sx?: SxProps<Theme>;
    onToggle?: (value: any) => void;
    helperText?: string;
    label?: string;
    readonly?: boolean;
    size?: 'small' | 'large' | 'medium'
    loading?: boolean;
    isChecked?: (value: any) => boolean;
    disabled?: boolean;
    onInputChange: (value: any, index: number) => void;
    formKey: keyof IHumanInteractionForm;
    fieldFn: (key: any) => IFormFieldMeta | null;
    index: number;
}

export const FormCheckBox = (props: IFormCheckBoxProps) => {
    const {index, fieldFn, formKey} = props;
    const field = fieldFn(formKey)!;

    return (
        <FormControl disabled={props.disabled} component="fieldset">
            <FormControlLabel
                label={<StyledFormFieldLabel>{props.label}</StyledFormFieldLabel>}
                control={
                    <Checkbox
                        size={props.size || undefined}
                        checked={field.value}
                        onChange={(e, checked) =>
                            props.onInputChange(checked, index)}
                    />
                }
            />
            {
                props.helperText &&
                <FormHelperText>
                    {props.helperText}
                </FormHelperText>
            }
        </FormControl>
    )
}
