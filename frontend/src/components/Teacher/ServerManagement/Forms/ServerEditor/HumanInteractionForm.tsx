import {Add, Delete, ErrorOutline} from "@mui/icons-material";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary, Box,
    Collapse,
    IconButton,
    MenuItem,
    OutlinedInput,
    Select,
    Stack,
    TextField, Tooltip,
    Typography,
    useTheme
} from "@mui/material";
import Button from "@mui/material/Button";
import React, {useState} from "react";
import {TransitionGroup} from "react-transition-group";
import {AgogeImage} from "../../../../../services/Server/image.model";
import {Protocols, SecurityModes} from "../../../../../types/Guacamole";
import {FormFields} from "../../../Specifications/NewEditor/utils/FormFields";
import {
    EmptyListItem,
    EmptyListItemText,
    FormCheckBox,
    FormGroup,
    FormGroupOutline,
    IHumanInteractionForm,
    IHumanInteractionFormKeys,
    IServerForm,
    StyledFormFieldLabel
} from "../FormFields";
import {IUseHumanInteractionForm} from "./useHumanInteractionForm";


interface Props {
    image: { pending: boolean, data: AgogeImage | null };
    imageForm: IServerForm;
    disableForm: boolean;
    interactionsForm: IUseHumanInteractionForm;
}

interface HInteractionState {
    ssh_key?: string;
    password?: string;
    username: string;
    usernameError: string;
    display: boolean;
    security_mode?: SecurityModes;
    protocol?: Protocols
}

export const HumanInteractionForm: React.FC<Props> = (props) => {
    const theme = useTheme();
    const interactionsForm: IUseHumanInteractionForm = props.interactionsForm;

    const [accordionStates, setAccordionStates] = useState<number[]>([0]);
    const [hInteractionState, setHInteractionState] = useState<Map<number, HInteractionState>>(new Map());

    const toggleAccordion = (index: number) => {
        if (accordionStates.includes(index)) {
            setAccordionStates(accordionStates.filter(idx => idx !== index));
        } else {
            setAccordionStates([...accordionStates, index]);
        }
    }

    const doesHaveErrors = (idx: number): boolean => {
        return interactionsForm.doesInteractionHaveErrors(idx);
    }

    const addInteraction = () => {
        interactionsForm.addInteraction();
        setAccordionStates([interactionsForm.forms.length]);
    }

    const removeInteraction = (index: number) => {
        interactionsForm.removeInteraction(index)

        const indexOfIndex = accordionStates.findIndex(idx => idx === index);
        setAccordionStates(
            accordionStates.filter(idx => idx !== indexOfIndex)
        );
    }

    const initializeHumanInteractionState = (
        hInteraction: IHumanInteractionForm | null,
        index: number
    ) => {
        if (!hInteractionState.has(index)) {
            setHInteractionState((prevState) => {
                const newState = new Map(prevState);
                newState.set(index, {
                    display: false,
                    password: "",
                    ssh_key: "",
                    username: "pantheon",
                    usernameError: "",
                    protocol: Protocols.SSH,
                    security_mode: SecurityModes.ANY
                });

                return newState;
            });
        }
    }

    const updateInteractionState = (index: number, updates: Partial<HInteractionState>) => {
        setHInteractionState((prevState) => {
            const newState = new Map(prevState);
            const currentState = newState.get(index) || {};
            newState.set(index, {...currentState, ...updates} as HInteractionState);
            return newState;
        });
    }

    const updateTextField = (
        event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
        key: keyof IHumanInteractionForm,
        idx: number
    ) => {
        const newValue = event.target.value;

        if (newValue.length === 0) return;

        if (key === IHumanInteractionFormKeys.USERNAME) {
            const usernameRegex = /^[a-zA-Z0-9_]([a-zA-Z0-9_.-]{0,18}[a-zA-Z0-9_]?)?$/;
            if (!usernameRegex.test(newValue)) {
                const errorMsg = "Invalid username. Please use only letters, numbers, underscores, " +
                    "periods, or hyphens. Your username must be between 3 and 20 characters long and cannot start " +
                    "or end with a period or space."
                updateInteractionState(idx, {usernameError: errorMsg});
                return;
            }
            updateInteractionState(idx, {usernameError: "", username: newValue});
        } else if (key === IHumanInteractionFormKeys.SSH_KEY) {
            updateInteractionState(idx, {ssh_key: newValue});
        } else if (key === IHumanInteractionFormKeys.PASSWORD) {
            updateInteractionState(idx, {password: newValue});
        }
        interactionsForm.handleInteractionValueChange(key, newValue, idx);
    }

    const handleDisplayChange = (value: any, idx: number) => {
        const checked = !!value;
        interactionsForm.handleInteractionValueChange(
            IHumanInteractionFormKeys.DISPLAY,
            checked,
            idx
        );
        updateInteractionState(idx, {display: value});
    }

    const handleProtocolChange = (value: any, idx: number) => {
        if (value !== undefined) {
            interactionsForm.handleInteractionValueChange(
                IHumanInteractionFormKeys.PROTOCOL,
                value.toString(),
                idx
            );
            updateInteractionState(idx, {protocol: value});
        }
    }

    const handleSecurityModeChange = (value: any, idx: number) => {
        if (value !== undefined) {
            interactionsForm.handleInteractionValueChange(
                IHumanInteractionFormKeys.SECURITY_MODE,
                value.toString(),
                idx
            );
            updateInteractionState(idx, {security_mode: value});
        }
    }

    const sshRequired = (currentState: IHumanInteractionForm): boolean => {
        return currentState[IHumanInteractionFormKeys.PROTOCOL].value == Protocols.SSH;
    }

    const enableSecurityMode = (currentState: IHumanInteractionForm): boolean => {
        const protocol = currentState[IHumanInteractionFormKeys.PROTOCOL].value;
        const display = !!currentState[IHumanInteractionFormKeys.DISPLAY].value

        return display && protocol === Protocols.RDP;
    }


    return (
        <>
            <FormFields alignItems={'center'}>
                <TransitionGroup style={{ width: '100%' }}>
                    {
                        interactionsForm.forms.map((hInteraction, index) => {
                            const currentState = interactionsForm.forms[index];

                            return (
                                <Collapse unmountOnExit key={index}>
                                    <Accordion disableGutters expanded={accordionStates.includes(index)} key={index}>
                                        <AccordionSummary
                                            sx={{ background: theme.palette.action.hover }}
                                            onClick={ () => toggleAccordion(index) }
                                        >
                                            <Stack
                                                width={'100%'}
                                                direction={'row'}
                                                alignItems={'center'}
                                                justifyContent={'space-between'}
                                            >
                                                <Stack direction={'row'} alignItems={'center'} gap={1}>
                                                    <Typography variant={'h6'}>Human Interaction {index + 1}</Typography>
                                                    {
                                                        doesHaveErrors(index) &&
                                                        <ErrorOutline color={'error'} fontSize={'small'} />
                                                    }
                                                    {
                                                        accordionStates.includes(index) ?
                                                            <ExpandLessIcon color={'primary'} size={'small'} /> :
                                                            <ExpandMoreIcon color={'primary'} size={'small'} />
                                                    }
                                                </Stack>
                                            </Stack>
                                            <span>
                                                <Tooltip
                                                    title={`Delete Human Interaction ${index + 1}`}
                                                    placement="bottom"
                                                    aria-label={`Delete human interaction ${index + 1} button`}
                                                >
                                                    <IconButton
                                                        color={'error'}
                                                        size={'small'}
                                                        onClick={(event) => {
                                                            event.stopPropagation();
                                                            removeInteraction(index);
                                                        }}
                                                    >
                                                        <Delete />
                                                    </IconButton>
                                                </Tooltip>
                                            </span>
                                        </AccordionSummary>
                                        <AccordionDetails>
                                            <FormFields>
                                                <FormGroupOutline showOverlay={props.disableForm}>
                                                    <FormGroup>
                                                        <StyledFormFieldLabel>Username</StyledFormFieldLabel>
                                                        <TextField
                                                            autoComplete={"username"}
                                                            key={`${index}-username`}
                                                            required
                                                            name={"username"}
                                                            type={"text"}
                                                            label={"Username"}
                                                            placeholder={"Custom user to be added for initial access. Defaults to pantheon."}
                                                            value={interactionsForm.getField(IHumanInteractionFormKeys.USERNAME, index).value}
                                                            helperText={
                                                                "Must start with an alphabetic character, " +
                                                                "cannot contains spaces or special characters, " +
                                                                "and cannot exceed 20 characters in length"
                                                            }
                                                            error={!!interactionsForm.getField(IHumanInteractionFormKeys.USERNAME, index).error}
                                                            onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => (
                                                                interactionsForm.handleInteractionValueChange(
                                                                    IHumanInteractionFormKeys.USERNAME,
                                                                    event.target.value,
                                                                    index
                                                                )
                                                            )}
                                                        />
                                                    </FormGroup>
                                                </FormGroupOutline>
                                                <FormGroupOutline showOverlay={props.disableForm}>
                                                    <FormGroup>
                                                        <StyledFormFieldLabel>Password</StyledFormFieldLabel>
                                                        <TextField
                                                            key={`${index}-password`}
                                                            required={false}
                                                            name={"password"}
                                                            type={"text"}
                                                            label={"Password"}
                                                            placeholder={
                                                                "Passphrase for current user. If none is given, a random " +
                                                                "passphrase is generated instead."
                                                            }
                                                            value={interactionsForm.getField(IHumanInteractionFormKeys.PASSWORD, index).value}
                                                            helperText={
                                                                "Must start with an alphanumeric character " +
                                                                "and cannot exceed 200 characters in length"
                                                        }
                                                            error={!!interactionsForm.getField(IHumanInteractionFormKeys.PASSWORD, index).error}
                                                            onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => (
                                                                interactionsForm.handleInteractionValueChange(
                                                                    IHumanInteractionFormKeys.PASSWORD,
                                                                    event.target.value,
                                                                    index
                                                                )
                                                            )}
                                                        />
                                                    </FormGroup>
                                                </FormGroupOutline>
                                                <FormGroupOutline showOverlay={props.disableForm}>
                                                    <FormGroup>
                                                        <StyledFormFieldLabel>SSH Key</StyledFormFieldLabel>
                                                        <TextField
                                                            key={`${index}-ssh-key`}
                                                            required={sshRequired(hInteraction)}
                                                            name={"ssh_key"}
                                                            type={"text"}
                                                            label={"SSH Public Key"}
                                                            placeholder={"SSH Public to associate with user"}
                                                            value={interactionsForm.getField(IHumanInteractionFormKeys.SSH_KEY, index).value}
                                                            slotProps={{htmlInput: {maxLength: 2048 }}}
                                                            onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => (
                                                                interactionsForm.handleInteractionValueChange(
                                                                    IHumanInteractionFormKeys.SSH_KEY,
                                                                    event.target.value,
                                                                    index
                                                                )
                                                            )}
                                                        />
                                                    </FormGroup>
                                                </FormGroupOutline>
                                                <FormGroupOutline showOverlay={props.disableForm}>
                                                    <Typography variant={"h6"}>Display Proxy Settings</Typography>
                                                    <FormGroup sx={{mt: 2}}>
                                                        <FormCheckBox
                                                            key={`${index}-display`}
                                                            index={index}
                                                            fieldFn={(key) => interactionsForm.getField(key, index)}
                                                            formKey={IHumanInteractionFormKeys.DISPLAY}
                                                            required={false}
                                                            name={"display"}
                                                            helperText={"Enable ability to connect to machine via display proxy."}
                                                            disabled={props.disableForm}
                                                            loading={props.disableForm}
                                                            isChecked={interactionsForm.getField(IHumanInteractionFormKeys.DISPLAY, index).value}
                                                            onInputChange={handleDisplayChange}
                                                            label={"Enable Display"}
                                                        />
                                                    </FormGroup>
                                                    <FormGroup sx={{my: 2}}>
                                                        <StyledFormFieldLabel>Connection Protocol</StyledFormFieldLabel>
                                                        <Select
                                                            size={'small'}
                                                            multiple={false}
                                                            value={interactionsForm.getField(IHumanInteractionFormKeys.PROTOCOL, index).value}
                                                            input={<OutlinedInput />}
                                                            onChange={
                                                                (e) => handleProtocolChange(e.target.value, index)
                                                            }
                                                            required={interactionsForm.getField(IHumanInteractionFormKeys.DISPLAY, index).value}
                                                        >
                                                            <MenuItem value={Protocols.SSH}>SSH</MenuItem>
                                                            <MenuItem value={Protocols.RDP}>RDP</MenuItem>
                                                            <MenuItem value={Protocols.VNC}>VNC</MenuItem>
                                                        </Select>
                                                    </FormGroup>
                                                    <FormGroup sx={{my: 2}}>
                                                        <StyledFormFieldLabel>Proxy Security Mode</StyledFormFieldLabel>
                                                        <Select
                                                            required={enableSecurityMode(currentState)}
                                                            disabled={!enableSecurityMode(currentState)}
                                                            size={'small'}
                                                            multiple={false}
                                                            value={interactionsForm.getField(IHumanInteractionFormKeys.SECURITY_MODE, index).value}
                                                            input={<OutlinedInput />}
                                                            onChange={
                                                                (e) => handleSecurityModeChange(e.target.value, index)
                                                            }
                                                        >
                                                            <MenuItem value={SecurityModes.ANY}>ANY</MenuItem>
                                                            <MenuItem value={SecurityModes.NLA}>NLA</MenuItem>
                                                            <MenuItem value={SecurityModes.RDP}>RDP</MenuItem>
                                                            <MenuItem value={SecurityModes.TLS}>TLS</MenuItem>
                                                        </Select>
                                                        <Typography variant={"subtitle2"} mx={1}>
                                                            Optional security mode for RDP connections only. Defaults to NLA.
                                                        </Typography>
                                                    </FormGroup>
                                                </FormGroupOutline>
                                            </FormFields>
                                        </AccordionDetails>
                                    </Accordion>
                                </Collapse>
                            )
                        })
                    }
                </TransitionGroup>

                {
                    interactionsForm.isEmpty() &&
                    <EmptyListItem sx={{padding: theme.spacing(2)}}>
                        <EmptyListItemText>
                            {
                                props.image.pending ? 'Loading ...': 'No Human Interaction'
                            }
                        </EmptyListItemText>
                    </EmptyListItem>
                }

                <Button
                    disabled={props.disableForm}
                    onClick={addInteraction}
                    color={'secondary'}
                    variant={'contained'}
                    sx={{ width: '70%', mb: 2}}
                    endIcon={<Add />}
                >
                    Add Human Interaction
                </Button>
            </FormFields>
        </>
    )
}