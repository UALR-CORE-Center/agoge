import {Add, Delete, ErrorOutline, Layers, Memory} from "@mui/icons-material";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Button,
    Collapse, debounce,
    IconButton,
    Stack,
    Typography,
    useTheme
} from "@mui/material";
import React, {useCallback, useEffect, useState} from "react";
import {TransitionGroup} from 'react-transition-group';


import {AgogeImage} from "../../../../../services/Server/image.model";
import {Network} from "../../../../../services/Specification/specification.model";
import {ServerMachineTypes} from "../../../../../services/Specification/specificationEdit.model";
import NumberInputField from "../../../../Common/FormInputs/NumberInputField";
import {validateDiskSize} from "../../../ServerManagement/Forms/ServerCreator/ServerFormValidators";
import {EmptyListItem, EmptyListItemText} from "../Review/ReviewCommonStyles";
import {CommonEditorChildrenProps} from "../utils/EditorTypes";
import {
    FormFields,
    FormGroup,
    FormGroupOutline,
    FormTextField,
    StyledFormFieldLabel,
    TableSelectField,
} from "../utils/FormFields";
import ServerFormSettings from "./ServerFormSettings";
import {IServerForm, ServerFormKeys} from "./ServerFormTypes";
import ServerNetworks from "./ServerNetworks";
import {IUseServerForm} from "./useServerForm";

interface Props extends CommonEditorChildrenProps {
    serverForm: IUseServerForm;
    images: { pending: boolean, data: AgogeImage[] };
    machineTypes: { pending: boolean, data: ServerMachineTypes[] };
    remoteNetworkInterfaces: Network[];
    localNetworkInterfaces: string[];
}

interface AgogeImageState {
    selectedImageRow: AgogeImage | null;
    selectedImageError: boolean;
    os: string;
    minDiskSize: number;
    name: string;
    nameError: string;
    diskSize: number;
    diskSizeError: string;
    selectedMachineTypeRow: ServerMachineTypes | null;
    selectedMachineTypeError: boolean;
    machineType: string;
}


const ServerForm: React.FC<Props> = ({
    serverForm,
    images,
    machineTypes,
    remoteNetworkInterfaces,
    localNetworkInterfaces,
    disableForm,
    specification
}: Props) => {
    const theme = useTheme();

    // Default toggle for the first network service
    const [accordionStates, setAccordionStates] = useState<number[]>([0]);

    // Manage all server states (both ImageSelectTable and MachineSelectTable)
    const [serverImageState, setServerImageState] = useState<Map<number, AgogeImageState>>(new Map());

    const toggleAccordion = (index: number) => {
        if (accordionStates.includes(index)) {
            setAccordionStates(accordionStates.filter(idx => idx !== index));
        } else {
            setAccordionStates([...accordionStates, index]);
        }
    }

    useEffect(() => {
        // revalidate form
    }, []);

    const initializeServerState = (server: IServerForm, index: number) => {
        if (!serverImageState.has(index)) {
            setServerImageState((prevState) => {
                const newState = new Map(prevState);
                newState.set(index, {
                    diskSize: server[ServerFormKeys.serverSettingsDiskSizeGb].value,
                    diskSizeError: '',
                    machineType: '',
                    minDiskSize: 10,
                    name: '',
                    nameError: '',
                    os: '',
                    selectedImageRow: null,
                    selectedImageError: true,
                    selectedMachineTypeRow: null,
                    selectedMachineTypeError: true,
                });

                return newState;
            });
        }
    };

    const updateServerState = (index: number, updates: Partial<AgogeImageState>) => {
        setServerImageState((prevState) => {
            const newState = new Map(prevState);
            const currentState = newState.get(index) || {};
            newState.set(index, {...currentState, ...updates} as AgogeImageState);
            return newState;
        });
    };

    const removeServer = (index: number) => {
        serverForm.removeServer(index);

        const indexOfIndex = accordionStates.findIndex(idx => idx === index);
        setAccordionStates(
            accordionStates.filter(idx => idx !== indexOfIndex)
        );
    }

    const addServer = () => {
        serverForm.addServer();
        setAccordionStates([serverForm.forms.length]);
    }

    const handleImageSelect = (selectedRow: any, index: number) => {
        if (selectedRow){
            updateServerState(index, {
                selectedImageRow: selectedRow,
                selectedImageError: false,
                name: selectedRow.name,
                os: selectedRow.os,
                minDiskSize: selectedRow.disk_size,
                diskSize: selectedRow.disk_size
            });
            serverForm.handleServerValueChange(ServerFormKeys.serverBaseImage, selectedRow?.image, index);
        } else {
            updateServerState(index, {
                selectedImageRow: null,
                selectedImageError: true,
                name: '',
                os: '',
                minDiskSize: 0,
                diskSize: 0,
            });
            serverForm.handleServerValueChange(ServerFormKeys.serverBaseImage, "", index);
        }

    }

    const handleMachineTypeSelect = (selectedRow: any, index: number) => {
        if (selectedRow) {
            updateServerState(index, {
                selectedMachineTypeRow: selectedRow,
                selectedMachineTypeError: false,
                machineType: selectedRow.id,
            });
            serverForm.handleServerValueChange(ServerFormKeys.serverSettingsMachineType, selectedRow?.id, index);
        } else {
            updateServerState(index, {
                selectedMachineTypeRow: null,
                selectedMachineTypeError: true,
                machineType: '',
            });
            serverForm.handleServerValueChange(ServerFormKeys.serverSettingsMachineType, "", index);
        }
    }

    const getServerState = (index: number) => {
        return serverImageState.get(index);
    }

    const getMinDiskSize = (index: number, currentState: AgogeImageState | undefined): number => {
        const server = currentState ? currentState : getServerState(index);
        if (server) {
            return server?.minDiskSize ? server.minDiskSize : 0
        } else {
            return 0;
        }
    }

    const handleDiskSizeChange = useCallback(
        debounce((index: number, value: number) => {
            const server = getServerState(index);
            const minDiskSize = server ? server.diskSize : 0;
            const error = validateDiskSize(value, minDiskSize);
            updateServerState(index, { diskSize: value, diskSizeError: error });
            serverForm.handleServerValueChange(ServerFormKeys.serverSettingsDiskSizeGb, value, index);
        }, 300),
        []
    );

    return (
        <FormFields alignItems={'center'}>
            <TransitionGroup style={{ width: '100%' }}>
                {
                    serverForm.forms.map((server, index) => {
                        initializeServerState(server, index);
                        const currentState = serverImageState.get(index);

                        return (
                            <Collapse unmountOnExit key={index}>
                                <Accordion disableGutters expanded={accordionStates.includes(index)} key={index}>
                                    <AccordionSummary
                                        sx={{ background: theme.palette.action.hover }}
                                        onClick={() => toggleAccordion(index)}
                                        aria-controls={`server-panel-${index}-content`}
                                        id={`server-panel-${index}-header`}
                                    >
                                        <Stack
                                            width={'100%'}
                                            direction={'row'}
                                            alignItems={'center'}
                                            justifyContent={'space-between'}
                                        >
                                            <Stack direction={'row'} alignItems={'center'} gap={1}>
                                                <Typography variant={'h6'}>Server {index + 1}</Typography>
                                                {
                                                    serverForm.doesServerHaveErrors(index) &&
                                                    <ErrorOutline color={'error'} fontSize={'small'} aria-label="This server has validation errors"/>
                                                }
                                                <IconButton
                                                    aria-label={
                                                        accordionStates.includes(index)
                                                            ? "Collapse server details"
                                                            : "Expand server details"
                                                    }
                                                    aria-expanded={accordionStates.includes(index)}
                                                    color={'primary'}
                                                    size={'small'}
                                                >
                                                    {
                                                        accordionStates.includes(index) ?
                                                            <ExpandLessIcon /> : <ExpandMoreIcon />
                                                    }
                                                </IconButton>
                                            </Stack>

                                            <IconButton
                                                aria-label={`Delete server ${index + 1}`}
                                                color={'error'}
                                                size={'small'}
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    removeServer(index);
                                                }}
                                            >
                                                <Delete />
                                            </IconButton>
                                        </Stack>
                                    </AccordionSummary>
                                    <AccordionDetails
                                        id={`server-panel-${index}-content`}
                                        aria-labelledby={`server-panel-${index}-header`}
                                    >
                                        <FormFields>
                                            <FormGroupOutline showOverlay={disableForm}>
                                                <FormGroup>
                                                    <StyledFormFieldLabel>Name</StyledFormFieldLabel>
                                                    <FormTextField
                                                        helpText={'Lowercase letters, numbers, hyphens allowed up to 52 characters'}
                                                        formKey={ServerFormKeys.serverName}
                                                        fieldFn={(key) => serverForm.getField(key, index)}
                                                        disabled={disableForm}
                                                        onInputChange={(field, value) => {
                                                            serverForm.handleServerValueChange(field, value, index);
                                                        }}
                                                    />
                                                </FormGroup>
                                            </FormGroupOutline>

                                            <FormGroupOutline showOverlay={disableForm}>
                                                <FormGroup>
                                                    <TableSelectField
                                                        disabled={images.pending}
                                                        fieldFn={(key) => serverForm.getField(key, index)}
                                                        formKey={ServerFormKeys.serverBaseImage}
                                                        index={index}
                                                        options={images.data}
                                                        onSelect={handleImageSelect}
                                                        required={true}
                                                        type={"image"}
                                                    />
                                                </FormGroup>

                                                <FormGroup mt={2}>
                                                    <TableSelectField
                                                        disabled={machineTypes.pending}
                                                        fieldFn={(key) => serverForm.getField(key, index)}
                                                        formKey={ServerFormKeys.serverSettingsMachineType}
                                                        index={index}
                                                        options={machineTypes.data}
                                                        onSelect={handleMachineTypeSelect}
                                                        required={false}
                                                        type={"mType"}
                                                    />
                                                </FormGroup>

                                                <FormGroup mt={2}>
                                                    <StyledFormFieldLabel>Disk Size (Gb)</StyledFormFieldLabel>
                                                    <NumberInputField
                                                        min={getMinDiskSize(index, currentState)}
                                                        max={400}
                                                        helperText="Size of attached server disk volume."
                                                        onChange={(event) => {
                                                            const value = Number(event.target.value);
                                                            handleDiskSizeChange(index, value);
                                                        }}
                                                        value={getMinDiskSize(index, currentState)}
                                                    />
                                                </FormGroup>
                                            </FormGroupOutline>

                                            <ServerFormSettings
                                                disableForm={disableForm}
                                                serverForm={serverForm}
                                                serverIndex={index}
                                                expanded={false}
                                            />

                                            <ServerNetworks
                                                disableForm={disableForm}
                                                server={server}
                                                serverForm={serverForm}
                                                serverIndex={index}
                                                localNetworkInterfaces={localNetworkInterfaces}
                                                remoteNetworkInterfaces={remoteNetworkInterfaces}
                                            />
                                        </FormFields>
                                    </AccordionDetails>
                                </Accordion>
                            </Collapse>
                        )
                    })
                }

            </TransitionGroup>

            {
                serverForm.isEmpty() &&
                <EmptyListItem sx={{padding: theme.spacing(2)}}>

                    <EmptyListItemText>
                        {
                            specification.pending ? 'Loading...' : 'No Servers'
                        }
                    </EmptyListItemText>

                </EmptyListItem>
            }

            <Button disabled={disableForm} onClick={addServer} variant={'contained'}
                sx={{ width: '70%', backgroundColor:'secondary.dark' }} endIcon={<Add />}>
                Add Server
            </Button>
        </FormFields>
    );
}

export default ServerForm;
