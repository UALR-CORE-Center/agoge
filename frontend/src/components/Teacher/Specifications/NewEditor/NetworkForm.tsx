import {Add, Delete, ErrorOutline} from "@mui/icons-material";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Button,
    Collapse,
    IconButton,
    Stack,
    Typography,
    useTheme
} from "@mui/material";
import { useModal } from "mui-modal-provider";
import React, {useState} from "react";
import {TransitionGroup} from 'react-transition-group';

import {UseFormsHook} from "../../../../hooks/useForms";
import SimpleSnackbar from "../../../Common/SnackBar/SnackBar";
import {EmptyListItemText} from "./Review/ReviewCommonStyles";
import {ServerFormKeys} from "./ServerForm/ServerFormTypes";
import {IUseServerForm} from "./ServerForm/useServerForm";
import {EditorFormFactory} from "./utils/EditorFormFactory";
import {CommonEditorChildrenProps, NetworkFormKeys} from "./utils/EditorTypes";
import {
    FormSwitch,
    FormFields,
    FormGroup,
    FormGroupOutline,
    FormTextField,
    StyledFormFieldLabel,
} from "./utils/FormFields";

interface Props extends CommonEditorChildrenProps {
    formHooks: UseFormsHook;
    serverForms: IUseServerForm;
}

const NetworkForm: React.FC<Props> = ({formHooks, disableForm, specification, serverForms}: Props) => {
    const theme = useTheme();
    const { showModal } = useModal();
    // default toggle first network service
    const [accordionStates, setAccordionStates] = useState<number[]>([0]);

    const toggleAccordion = (index: number) => {
        if (accordionStates.includes(index)) {
            setAccordionStates(accordionStates.filter(idx => idx !== index));
        } else {
            setAccordionStates([...accordionStates, index]);
        }
    };

    const isNetworkUsedByAnyServer = (networkName: string): boolean => {
        if (!serverForms.forms || serverForms.forms.length === 0) {
            return false;  // No servers, so the network can't be in use
        }

        return serverForms.forms.some(serverForm => {
            const networkInterfaces = serverForm[ServerFormKeys.serverNetworks];
            return networkInterfaces.some((networkInterface: any) => networkInterface[ServerFormKeys.serverNicNetwork].value === networkName);
        });
    };

    const removeNetworkService = (index: number) => {
        const networkName = formHooks.forms![index][NetworkFormKeys.networkName].value;

        if (isNetworkUsedByAnyServer(networkName)) {
            showModal(SimpleSnackbar, { message: `Cannot delete the network "${networkName}" because it is in use by one or more servers.`, severity: "error" });
            return;
        }

        formHooks.removeForm(index);

        const indexOfIndex = accordionStates.findIndex(idx => idx === index);
        setAccordionStates(accordionStates.filter(idx => idx !== indexOfIndex));
    };

    const addNetworkService = () => {
        formHooks.addForm(
            EditorFormFactory.generateNetworkForm(
                formHooks.forms?.length === 0 ? { name: 'external' } : null
            )
        );

        // Looks strange without .length - 1, but required to work
        setAccordionStates([formHooks.forms!.length]);
    };

    return (
        <FormFields alignItems={'center'}>
            <TransitionGroup style={{ width: '100%' }}>
                {
                    formHooks.forms?.map((networkServiceForm, index) => {
                        return (
                            <Collapse key={index} unmountOnExit>
                                <Accordion disableGutters expanded={accordionStates.includes(index)}>
                                    <AccordionSummary
                                        sx={{
                                            background: theme.palette.action.hover,
                                        }}

                                        onClick={() => toggleAccordion(index)}
                                        aria-controls={`network-panel-${index}-content`}
                                        id={`network-panel-${index}-header`}
                                        aria-expanded={accordionStates.includes(index)}
                                        aria-label={
                                            accordionStates.includes(index)
                                                ? `Collapse Network ${index + 1}`
                                                : `Expand Network ${index + 1}`
                                        }
                                    >
                                        <Stack width={'100%'} direction={'row'} alignItems={'center'}
                                            justifyContent={'space-between'}>
                                            <Stack direction={'row'} alignItems={'center'} gap={1}>
                                                <Typography variant={'h6'}>Network {index}</Typography>
                                                {
                                                    formHooks.doesFormHaveErrors(index) &&
                                                    <ErrorOutline color={'error'} fontSize={'small'} />
                                                }
                                            </Stack>

                                            {
                                                (((formHooks.forms || []).length === 1 && index === 0) || index > 0) &&
                                                <IconButton
                                                    disabled={disableForm}
                                                    color={'error'}
                                                    size={'small'}
                                                    aria-label={`Delete Network ${index}`}
                                                    onClick={(event) => {
                                                        event.stopPropagation();
                                                        removeNetworkService(index);
                                                    }}
                                                >
                                                    <Delete />
                                                </IconButton>
                                            }
                                        </Stack>
                                    </AccordionSummary>
                                    <AccordionDetails id={`network-panel-${index}-content`} aria-labelledby={`network-panel-${index}-header`}>
                                        <FormFields>
                                            <FormGroupOutline showOverlay={disableForm}> <FormGroup>
                                                <StyledFormFieldLabel>Name</StyledFormFieldLabel>
                                                <FormTextField
                                                    helpText={index === 0 ? 'External is required as the first one' : 'Lowercase letters, numbers, hyphens allowed up to 52 characters'}
                                                    formKey={NetworkFormKeys.networkName}
                                                    disabled={disableForm}
                                                    readOnly={index === 0}
                                                    fieldFn={(key) => formHooks.forms![index][key]}
                                                    onInputChange={(field, value) => {
                                                        formHooks.handleInputChange(field, value, index);
                                                    }}
                                                />
                                            </FormGroup>
                                            </FormGroupOutline>

                                            <FormGroupOutline showOverlay={disableForm}> <FormGroup>
                                                <StyledFormFieldLabel>IPv4 Range</StyledFormFieldLabel>
                                                <FormTextField
                                                    helpText={'The address range for this subnet, in CIDR notation. Use a standard private VPC network address range: for example, 10.0.0.0/9.'}
                                                    formKey={NetworkFormKeys.networkSubnets}
                                                    disabled={disableForm}
                                                    fieldFn={(key) => formHooks.forms![index][key]}
                                                    onInputChange={(field, value) => {
                                                        formHooks.handleInputChange(field, value, index);
                                                    }}
                                                />

                                                <FormSwitch formKey={NetworkFormKeys.networkPromiscuous}
                                                    fieldFn={(key) => formHooks.forms![index][key]}
                                                    disabled={disableForm}
                                                    onInputChange={(field, value) => {
                                                        formHooks.handleInputChange(field, value, index);
                                                    }}
                                                    label={"Promiscuous Mode"}
                                                    helpText={'Enables promiscuous mode for all servers attached to subnet.'} />
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
                formHooks.forms?.length == 0 &&
                <EmptyListItemText>
                    {specification.pending ?
                        'Loading...' : 'No Networks'
                    }
                </EmptyListItemText>
            }

            <Button disabled={disableForm} onClick={addNetworkService} variant={'contained'} color={'secondary'}
                sx={{ width: '70%'}}
                endIcon={<Add />}>
                Add Network
            </Button>
        </FormFields>
    );
};

export default NetworkForm;
