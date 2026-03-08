import {ServerFormKeys, IServerFormNetworks} from "./ServerFormTypes";
import React, {useState} from "react";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Collapse, IconButton,
    ListItem,
    Stack,
    Typography,
    useTheme
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
    FormAutocompleteField, FormCheckBox, FormFields,
    FormGroup, FormGroupOutline,
    FormMuliTextField,
    FormTextField,
    StyledFormFieldLabel
} from "../utils/FormFields";
import {Clear, ErrorOutline} from "@mui/icons-material";
import {Network} from "../../../../../services/Specification/specification.model";
import serverFormSettings from "./ServerFormSettings";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import {IUseServerForm} from "./useServerForm";

interface Props {
    serverForm: IUseServerForm,
    serverIndex: number;
    nicIndex: number;
    nic: IServerFormNetworks,
    remoteNetworkInterfaces: Network[]
    localNetworkInterfaces: string[];
    disableForm: boolean;
}

const ServerFormNic: React.FC<Props> = ({
                                            serverForm,
                                            serverIndex,
                                            nicIndex,
                                            disableForm,
                                            remoteNetworkInterfaces,
                                            localNetworkInterfaces
                                        }) => {
    const [opened, setOpened] = useState(true)
    const theme = useTheme();

    const formatSelectedNicName = (): string => {
        const name = serverForm.getField(ServerFormKeys.serverNicNetwork, serverIndex, nicIndex).value;
        const ip = serverForm.getField(ServerFormKeys.serverNicIPv4Addr, serverIndex, nicIndex).value;

        if (!!name && !!ip) {
            return `(${name} (${ip}))`
        }

        if (!!name && !(!!ip)) {
            return "(" + name + ")";
        }

        if (!(!!name) && !!ip) {
            return "(" + ip + ")";
        }

        return '';
    }

    return (

        <FormGroupOutline showOverlay={disableForm} sx={{padding: theme.spacing(1)}}>
            <Stack sx={{cursor: 'pointer'}} onClick={() => setOpened(!opened)} direction={'row'} alignItems={'center'}>

                <Stack direction={'row'} alignItems={'center'} gap={1}>
                    <IconButton
                        color={'primary'}
                        size={'small'}
                        aria-label={opened ? `Collapse NIC ${nicIndex}` : `Expand NIC ${nicIndex}`}>
                        {opened ? <ExpandLessIcon/> : <ExpandMoreIcon/>}
                    </IconButton>

                    <Stack direction={'row'} alignItems={'center'} gap={1}>
                        <StyledFormFieldLabel>NIC {nicIndex}</StyledFormFieldLabel>
                        <Typography variant={'subtitle1'}
                                    color={'text.secondary'}>{formatSelectedNicName()}</Typography>
                        {
                            serverForm.doesNicHaveErrors(serverForm.forms[serverIndex][ServerFormKeys.serverNetworks][nicIndex]) &&
                            <ErrorOutline fontSize={'small'} color={'error'}/>
                        }
                    </Stack>
                </Stack>

                <IconButton sx={{ml: 'auto'}} onClick={() => serverForm.removeNic(serverIndex, nicIndex)}
                            color={'error'} size={'small'}>
                    <Clear/>
                </IconButton>
            </Stack>

            <Collapse in={opened}>
                <FormFields gap={3} sx={{paddingX: 1, paddingY: 2}}>
                    <FormGroup>
                        <StyledFormFieldLabel>Network</StyledFormFieldLabel>
                        <FormAutocompleteField
                            options={remoteNetworkInterfaces}
                            isOptionEqualToValue={(option, value) => {
                                return option?.name == value;
                            }}
                            disabled={disableForm}
                            formKey={ServerFormKeys.serverNicNetwork}
                            fieldFn={(key) => serverForm.getField(key, serverIndex, nicIndex)}
                            onInputChange={(field, value: Network) => {
                                serverForm.handleNicValueChange(field as keyof IServerFormNetworks, value?.name || '', serverIndex, nicIndex)
                            }}
                            noOptionsTextFn={(input: string) => {
                                const matches = localNetworkInterfaces.filter(v => v.toLowerCase().startsWith(input.toLowerCase()));
                                if (!!input && matches.length) {
                                    if (matches.length === 1) {
                                        return `NIC '${matches[0]}' exists locally, but must be saved to use it.`;
                                    } else {
                                        return `One or more local NICs exist locally but must be saved before they can be used.`;
                                    }
                                }
                            }}
                            renderOption={(props, option) => {
                                const {key, ...restProps} = props;
                                return <ListItem {...props} key={key}
                                                 divider>{option.name} ({option.subnets![0]?.ip_subnet})</ListItem>
                            }}
                            getOptionLabel={(option) => {
                                const nic = remoteNetworkInterfaces.find((n) => n?.name == option);
                                if (nic !== undefined)
                                    return `${nic!.name} (${nic!.subnets![0]?.ip_subnet})`

                                return option?.name || '';
                            }}
                        />
                    </FormGroup>

                    <FormGroup>
                        <StyledFormFieldLabel>IPv4 Address</StyledFormFieldLabel>
                        <FormTextField
                            helpText={'Enter the server IP address for the selected subnet.'}
                            placeholder={'10.1.1.30'}
                            formKey={ServerFormKeys.serverNicIPv4Addr}
                            fieldFn={(key) => serverForm.getField(key, serverIndex, nicIndex)}
                            disabled={disableForm}
                            onInputChange={(field, value) => {
                                serverForm.handleNicValueChange(field, value, serverIndex, nicIndex)
                            }}
                        />
                    </FormGroup>

                    <FormGroup>
                        <StyledFormFieldLabel>IP Aliases</StyledFormFieldLabel>
                        <FormMuliTextField
                            rows={3}
                            placeholder={'Comma delimited list of IPs e.g 172.2.0.1,172.3.0.1'}
                            helpText={'Assign multiple IP values to NIC and enable nested virtualization for server. Each IP must be comma delimited with no spaces.'}
                            formKey={ServerFormKeys.serverNicIpAliases}
                            fieldFn={(key) => serverForm.getField(key, serverIndex, nicIndex)}
                            disabled={disableForm}
                            onInputChange={(field, value) => {
                                serverForm.handleNicValueChange(field as keyof IServerFormNetworks, value, serverIndex, nicIndex)
                            }}
                        />
                    </FormGroup>


                    <FormCheckBox
                        formKey={ServerFormKeys.serverNicEnableExternalNat}
                        fieldFn={(key) => serverForm.getField(key, serverIndex, nicIndex)}
                        onInputChange={(field, value) => {
                            serverForm.handleNicValueChange(field, value, serverIndex, nicIndex)
                        }}
                        disabled={disableForm || serverForm.getField(ServerFormKeys.serverEnableDirectConnections, serverIndex, nicIndex)?.value}
                        size={'small'}
                        label={"Enable External NAT"}
                        helpText={'Allows server to be accessible via ephemeral external IP.'}
                    />

                    <FormCheckBox
                        formKey={ServerFormKeys.serverEnableDirectConnections}
                        fieldFn={(key) => serverForm.getField(key, serverIndex, nicIndex)}
                        disabled={disableForm}
                        onInputChange={(field, value) => {
                            serverForm.handleNicValueChange(field, value, serverIndex, nicIndex)
                        }}

                        size={'small'}
                        label={"Enable Direct Connections"}
                        helpText={'Allow users to connect via SSH or RDP without using a proxy-machine. Requires `External NAT` to be True.'}
                    />

                </FormFields>
            </Collapse>


        </FormGroupOutline>
    )
}

export default ServerFormNic;
