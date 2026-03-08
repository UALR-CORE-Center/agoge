import {
    Checkbox,
    CircularProgress,
    debounce,
    FormControl,
    FormControlLabel,
    FormHelperText,
    ListItemText,
    MenuItem,
    OutlinedInput,
    Paper,
    Radio,
    RadioGroup,
    Select,
    Stack,
    styled,
    Switch,
    TextField,
    Theme,
    Typography
} from "@mui/material";
import Autocomplete from '@mui/material/Autocomplete';
import {lighten, SxProps} from "@mui/system";
import React, {useEffect, useRef, useState} from "react";
import {IUseFormHook} from "../../../../../hooks/useForm";
import {UseFormsHook} from "../../../../../hooks/useForms";
import {IFormFieldMeta, FormType} from "../../../../../types/Form";
import {SelectImageTable} from "../ServerForm/SelectImageTable";
import {SelectMachineTypeTable} from "../ServerForm/SelectMachineTypeTable";

interface FormRowProps {
    gap?: number;
    theme?: any;

    alignItems?: string;
}


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
}));


export const FormGroupOutlineNoPadding = styled(Paper, {
    shouldForwardProp: (prop) => prop !== 'theme' && prop !== 'showOverlay',
})<{ theme?: Theme, showOverlay?: boolean }>(({theme, showOverlay}) => ({
    background: 'transparent',
    boxShadow: 'none',
    opacity: showOverlay ? .25 : 1,
}));


export const FormFields = styled(Stack, {
    shouldForwardProp: (prop) => prop !== 'theme' && prop !== 'gap',
})<FormRowProps>(({theme, gap}) => ({
    gap: theme.spacing(gap || 3),
    margin: `${theme.spacing(2)} 0`
}));

export const FormRow = styled(Stack, {
    shouldForwardProp: (prop) => prop !== 'theme' && prop !== 'gap' && prop !== 'alignItems',
})<FormRowProps>(({theme, gap, alignItems}) => ({
    width: '100%',
    flexDirection: 'column', // Set the default value to 'column'
    '@media (min-width: 600px)': {
        flexDirection: 'column', // Set the value for xs and sm screens
    },
    '@media (min-width: 960px)': {
        flexDirection: 'row', // Set the value for md (medium) and larger screens
    },
    gap: theme.spacing(gap || 1),
    alignItems: alignItems || 'center'
}));


export const StyledFormGroupLabel = styled(Typography)(({theme}) => ({
    fontWeight: 'bold',
    fontSize: '1.1em'
}));

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


interface IFormTextFieldProps {
    placeholder?: string;
    formKey: keyof FormType;

    // // Option 1
    // formHook?: UseFormHook;
    //
    // // Option 2
    // formHooks?: UseFormsHook;
    // formHooksIndex?: number;

    // Option 3
    fieldFn: (key: any) => IFormFieldMeta | null;
    onInputChange: (field: any, value: any) => void;

    readOnly?: boolean
    disabled?: boolean
    helpText?: string;
    type?: string;
    required?: boolean;
    endAdornment?: JSX.Element;
}

export const FormTextField = (props: IFormTextFieldProps) => {
    const {formKey, fieldFn, onInputChange} = props;
    const [inputFocused, setInputFocused] = useState(false);

    const field = fieldFn(formKey)!;
    return (
        <StyledFormTextField value={field?.value || ''}
                             placeholder={props.placeholder}
                             type={props.type}
                             onFocus={() => setInputFocused(true)}
                             onBlur={() => setInputFocused(false)}
                             error={!!field?.error}
                             helperText={field?.error || props.helpText}
                             disabled={props.disabled}
                             InputProps={{readOnly: props.readOnly, endAdornment: props.endAdornment}}
                             onChange={(e) => {
                                 onInputChange(formKey, e.target.value);
                             }}
                             size={'small'}
                             variant={'outlined'}/>
    )
}


interface IFormTableSelectProps {
    disabled?: boolean;
    formKey: keyof FormType;
    fieldFn: (key: any) => IFormFieldMeta | null;
    helpText?: string;
    index: number;
    onSelect: (selectedRow: any, index: number) => void;
    options: any[];
    required?: boolean;
    type: "image" | "mType";
}

export const TableSelectField = (props: IFormTableSelectProps) => {
    const {formKey, fieldFn, onSelect, options} = props;
    const field = fieldFn(formKey)!;

    const render = () => {
        if (props.type === "image") {
            return (
                <SelectImageTable
                    loading={!!props.disabled}
                    images={options}
                    onSelect={onSelect}
                    index={props.index}
                    required={props.required}
                    formField={field}
                />
            );
        } else if (props.type === "mType") {
            return (
                <SelectMachineTypeTable
                    loading={!!props.disabled}
                    options={options}
                    onSelect={onSelect}
                    index={props.index}
                    required={props.required}
                    formField={field}
                />
            );
        }
        return null;
    }

    return (render());
}


interface IMultiTextField extends IFormTextFieldProps {
    placeholder?: string;
    readOnly?: boolean
    disabled?: boolean
    type?: string;
    required?: boolean
    rows?: number;
    helpText?: string;
}


export const FormMuliTextField = (props: IMultiTextField) => {
    const {formKey, fieldFn} = props;
    const [inputFocused, setInputFocused] = useState(false);

    const formField = fieldFn(formKey)!;
    return (
        <StyledFormTextField value={formField.value}
                             placeholder={props.placeholder}
                             type={props.type}
                             onFocus={() => setInputFocused(true)}
                             onBlur={() => setInputFocused(false)}
                             rows={props.rows || 5}
                             multiline
                             error={!!formField.error}
                             helperText={formField.error || props.helpText}
                             disabled={props.disabled}
                             InputProps={{readOnly: props.readOnly}}
                             onChange={(e) => {
                                 props.onInputChange(formKey, e.target.value);
                             }}
                             size={'small'}
                             variant={'outlined'}/>
    )
}

interface IFormAutocompleteProps extends IFormTextFieldProps {
    sx?: SxProps<Theme>;
    options: any[],
    getOptionLabel?: (option: any) => string
    renderOption?: (props: any, option: any) => React.ReactElement
    onSelection?: (value: any) => void;
    // validation fn to see if input string is valid
    inputValue?: string;
    inputValueValidation?: (value: string) => boolean;
    setInputValue?: (v: string) => void;
    open?: boolean;

    isOptionEqualToValue?: (option: any, value: any) => boolean;

    onInputChange: (field: string | number, value: any) => void;
    loading?: boolean;
    disableSelectBtn?: boolean;
    freeSolo?: boolean;
    allowClearTextBtn?: boolean
    noOptionsTextFn?: (value: string) => string | undefined;
}

/**
 *
 * Loading indicator will only be shown IF loading is present in the props.
 *
 * @param props
 * @constructor
 */

export const FormAutocompleteField: React.FC<IFormAutocompleteProps> = (props: IFormAutocompleteProps) => {
    const [inputFocused, setInputFocused] = useState(false);

    /**
     *
     * This could be optimized by not making an extra query search when the option the user is typing is right there
     *
     */

    const [userIsTyping, setUserIsTyping] = useState(false);

    const {formKey, fieldFn} = props;
    const [input, setInput] = useState(props.inputValue || '');


    const debouncedOnChange = useRef(
        debounce((value: string) => {
            props.setInputValue!(value);
            setUserIsTyping(false);
        }, 500)
    ).current;


    useEffect(() => {
        return () => {
            debouncedOnChange.clear();
        };
    }, [debouncedOnChange]);


    const loading = (userIsTyping || props.loading) && props.loading !== undefined;
    const field = fieldFn(formKey)!;


    const handleInputChange = (value: string) => {
        props.onInputChange(formKey, value);
    }

    return (
        <Autocomplete
            sx={{...props.sx}}
            onFocus={() => setInputFocused(true)}
            onBlur={() => setInputFocused(false)}
            value={(!(!!field?.value) || props.loading) ? null : field.value}
            onChange={(event: any, newValue: any | null) => {
                handleInputChange(newValue || '')

                if (props.onSelection) {
                    props.onSelection(newValue);
                }

                setUserIsTyping(false);

            }}
            isOptionEqualToValue={props.isOptionEqualToValue}
            inputValue={input}
            autoHighlight
            freeSolo={props.freeSolo}
            readOnly={props.readOnly}
            renderOption={props.renderOption}
            getOptionLabel={props.getOptionLabel}
            disableClearable={props.allowClearTextBtn}
            open={props.open}
            disabled={props.disabled}
            options={props.options}
            noOptionsText={props.noOptionsTextFn ? props.noOptionsTextFn(input) : undefined}
            onInputChange={(e, newInputValue) => {
                // Input value is passed in when we're actively making API calls.
                // there is no need to track if user is typing if no input value is
                // passed in.
                if (!userIsTyping && props.inputValue)
                    setUserIsTyping(true); // Set loading state when input changes

                if (props.inputValueValidation) {
                    const isValid = props.inputValueValidation(newInputValue);

                    if (isValid && props.onSelection) {
                        props.onSelection(newInputValue);
                        setUserIsTyping(false);
                    } else if ((isValid || newInputValue?.trim() === '') || props.freeSolo) {
                        handleInputChange(newInputValue)
                    }

                } else if (props.freeSolo)
                    debouncedOnChange(newInputValue)

                if (props.setInputValue) {
                    debouncedOnChange(newInputValue)
                }

                setInput(newInputValue)
            }}
            loading={loading}
            renderInput={(params) => {
                return (
                    <StyledFormTextField
                        placeholder={props.placeholder}
                        error={!!field?.error}
                        helperText={field?.error || props.helpText}
                        type={props.type}
                        {...params}
                        disabled={props.disabled}
                        InputProps={{
                            ...params.InputProps,
                            inputProps: {
                                ...params.inputProps,
                                readOnly: props.readOnly,
                            },
                            endAdornment: (
                                <React.Fragment>
                                    {loading ?
                                        <CircularProgress color={'info'} size={15}/> : params.InputProps.endAdornment}
                                    {!props.disableSelectBtn && params.InputProps.endAdornment}
                                </React.Fragment>
                            ),
                        }}
                        size="small"
                        variant="outlined"

                    />
                )
            }}

        />
    );
};


interface IFormMultiSelectProps extends IFormTextFieldProps {
    sx?: SxProps<Theme>;
    options: any[],
    onSelection?: (value: any) => void;
    helpText?: string;
    open?: boolean;
    renderValueOverrideText?: string;
    readOnly?: boolean;
    loading?: boolean;
    isSelected?: (value: any) => boolean;
    onRemove?: (values: any, value: string) => void;
}

export const FormMultiSelect = (props: IFormMultiSelectProps) => {
    const {formKey, fieldFn} = props;

    const isSelected = (value: any): boolean => {
        if (props.isSelected) {
            return props.isSelected(value);
        } else {
            return field.value.indexOf(value) > -1
        }
    }

    const handleChange = (values: string[]) => {
        if (values.length > 0) {
            const value = values[values.length - 1];
            if (isSelected(value) && props.onRemove) {
                props.onRemove(values, values[values.length - 1]);
                return;
            }
        }

        if (props.onSelection) {
            props.onSelection(values);
        } else {
            props.onInputChange(formKey, values)
        }
    };


    const field = fieldFn(formKey)!;
    return (
        <FormControl disabled={props.disabled} error={!!field?.error}>
            <Select
                size={'small'}
                multiple
                value={field?.value || []}
                // todo implement if you don't want to actually override the text
                renderValue={() => props.renderValueOverrideText || ''}
                onChange={(e) => handleChange(e.target.value)}
                input={<OutlinedInput/>}
                displayEmpty
            >
                {props.options.map((name) => (
                    <MenuItem divider key={name} value={name}>
                        <Checkbox checked={isSelected(name)}/>
                        <ListItemText primary={name}/>
                    </MenuItem>
                ))}
            </Select>

            {field?.error && (
                <FormHelperText>{field?.error}</FormHelperText>
            )}
        </FormControl>
    )
}


interface IFormSwitchProps extends IFormTextFieldProps {
    sx?: SxProps<Theme>;
    onToggle?: (value: any) => void;
    helpText?: string;
    label?: string;
    readOnly?: boolean;
    loading?: boolean;
    isChecked?: (value: any) => boolean;
}

export const FormSwitch = (props: IFormSwitchProps) => {
    const {formKey, fieldFn} = props;


    const field = fieldFn(formKey)!;
    return (
        <FormControl disabled={props.disabled} component="fieldset">
            <FormControlLabel
                label={<StyledFormFieldLabel>{props.label}</StyledFormFieldLabel>}
                control={
                    <Switch
                        checked={field.value}
                        onChange={(e, checked) =>
                            props.onInputChange(formKey, checked)
                        }
                    />
                }
            />
            {
                props.helpText &&
                <FormHelperText>
                    {props.helpText}
                </FormHelperText>
            }
        </FormControl>
    )
}


interface IFormCheckBoxProps extends IFormTextFieldProps {
    sx?: SxProps<Theme>;
    onToggle?: (value: any) => void;
    helpText?: string;
    label?: string;
    readOnly?: boolean;
    size?: 'small' | 'large' | 'medium'
    loading?: boolean;
    isChecked?: (value: any) => boolean;
}

export const FormCheckBox = (props: IFormCheckBoxProps) => {
    const {formKey, fieldFn} = props;
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
                            props.onInputChange(formKey, checked)}
                    />
                }
            />
            {
                props.helpText &&
                <FormHelperText>
                    {props.helpText}
                </FormHelperText>
            }
        </FormControl>
    )
}


interface IFormRadioBtnsProps extends IFormTextFieldProps {
    sx?: SxProps<Theme>;
    onToggle?: (value: any) => void;
    helpText?: string;
    label?: string;
    readOnly?: boolean;
    size?: 'small' | 'large' | 'medium'
    options: { label: string, value: string }[]
}

export const FormRadioBtns = (props: IFormRadioBtnsProps) => {
    const {formKey, fieldFn} = props;
    const field = fieldFn(formKey)!;
    return (
        <FormControl disabled={props.disabled} component="fieldset">
            {
                props.label && <StyledFormFieldLabel>{props.label}</StyledFormFieldLabel>
            }
            <RadioGroup value={field.value} onChange={(e, value) => props.onInputChange(formKey, value)} row>
                {
                    props.options.map((opt) =>
                        <FormControlLabel key={opt.value} value={opt.value} control={<Radio/>}
                                          label={<StyledFormFieldLabel>{opt.label}</StyledFormFieldLabel>}/>
                    )
                }
            </RadioGroup>

            {
                props.helpText &&
                <FormHelperText>
                    {props.helpText}
                </FormHelperText>
            }
        </FormControl>
    )
}

