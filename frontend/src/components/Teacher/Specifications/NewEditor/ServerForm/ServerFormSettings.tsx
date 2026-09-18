import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {Accordion, AccordionDetails, AccordionSummary, Box, Stack, useTheme} from "@mui/material";
import React from "react";
import {
    FormCheckBox,
    FormMuliTextField,
    FormTextField,
    StyledFormFieldLabel
} from "../utils/FormFields";
import {IServerForm, ServerFormKeys} from "./ServerFormTypes";
import {IUseServerForm} from "./useServerForm";

interface Props {
    serverForm: IUseServerForm,
    serverIndex: number;
    disableForm: boolean;
    expanded: boolean;
}

const ServerFormSettings: React.FC<Props> = ({
    serverForm,
    serverIndex,
    disableForm,
    expanded,
}) => {
    const theme = useTheme();
    return (
        <Accordion elevation={3}>
            <AccordionSummary
                expandIcon={<ExpandMoreIcon/>}
                sx={{background: theme.palette.action.hover}}
                aria-controls={`server-settings-${serverIndex}-content`}
                aria-label={
                    expanded
                        ? "Collapse server settings"
                        : "Expand server settings"
                }
                id={`server-settings-${serverIndex}-header`}
            >
                <StyledFormFieldLabel>Settings</StyledFormFieldLabel>
            </AccordionSummary>
            <AccordionDetails
                id={`server-settings-${serverIndex}-content`}
                aria-labelledby={`server-settings-${serverIndex}-header`}
            >
                <Box sx={{paddingX: 1}}>
                    <FormCheckBox
                        formKey={ServerFormKeys.serverSettingHide}
                        disabled={disableForm}
                        fieldFn={(key) => serverForm.getField(key, serverIndex)}
                        onInputChange={(field, value) => {
                            serverForm.handleServerValueChange(field, value, serverIndex)
                        }}
                        label={"Hide Server"}
                        size={'small'}
                        helpText={'Hide server from server list on student pages. Server is still visible from the network view.'}
                    />

                    <FormCheckBox
                        formKey={ServerFormKeys.serverSettingCommunity}
                        fieldFn={(key) => serverForm.getField(key, serverIndex)}
                        disabled={disableForm}
                        onInputChange={(field, value) => {
                            serverForm.handleServerValueChange(field, value, serverIndex)
                        }}
                        size={'small'}
                        label={"Community Server"}
                        helpText={'Whether this server should be a shared server in a community build unit. Defaults to unshared.'}
                    />

                    <FormCheckBox
                        formKey={ServerFormKeys.serverSettingWireGuardGateway}
                        fieldFn={(key) => serverForm.getField(key, serverIndex)}
                        disabled={disableForm}
                        onInputChange={(field, value) => {
                            serverForm.handleServerValueChange(field, value, serverIndex)
                        }}
                        size={'small'}
                        label={"WireGuard Gateway"}
                        helpText={
                            'Marks the shared community server as the WireGuard next hop. ' +
                            'This also enables Community Server and IP Forwarding.'
                        }
                    />

                    <FormCheckBox
                        formKey={ServerFormKeys.serverSettingCanIpForward}
                        fieldFn={(key) => serverForm.getField(key, serverIndex)}
                        disabled={disableForm}
                        onInputChange={(field, value) => {
                            serverForm.handleServerValueChange(field, value, serverIndex)
                        }}
                        size={'small'}
                        label={"Enable IP Forwarding"}
                        helpText={'Allows this VM to forward packets as a router. The guest operating system must also enable forwarding.'}
                    />

                    <FormCheckBox
                        formKey={ServerFormKeys.serverSettingDeny}
                        fieldFn={(key) => serverForm.getField(key, serverIndex)}
                        disabled={disableForm}
                        onInputChange={(field, value) => {
                            serverForm.handleServerValueChange(field, value, serverIndex)
                        }}

                        size={'small'}
                        label={"Deny Outbound"}
                        helpText={
                            'Allows incoming connections (i.e. SSH or RDP), but denies all traffic from within ' +
                            'the server outwards. Does not block traffic directed towards attached local networks.'
                        }
                    />

                    <Stack gap={1} mt={2}>
                        <StyledFormFieldLabel>Network Tags</StyledFormFieldLabel>
                        <FormTextField
                            placeholder={'wireguard-gateway, lab-router'}
                            helpText={'Comma-separated Google Cloud network tags.'}
                            formKey={ServerFormKeys.serverSettingTags}
                            fieldFn={(key) => serverForm.getField(key, serverIndex)}
                            disabled={disableForm}
                            onInputChange={(field, value) => {
                                serverForm.handleServerValueChange(field, value, serverIndex)
                            }}
                        />
                    </Stack>

                    <Stack gap={1} mt={2}>
                        <StyledFormFieldLabel>Startup Script</StyledFormFieldLabel>
                        <FormMuliTextField
                            rows={6}
                            placeholder={'#!/bin/bash'}
                            helpText={'Optional inline Compute Engine startup script.'}
                            disabled={disableForm}
                            formKey={ServerFormKeys.serverStartupScript}
                            fieldFn={(key) => serverForm.getField(key, serverIndex)}
                            onInputChange={(field, value) => {
                                serverForm.handleServerValueChange(
                                    field as keyof IServerForm,
                                    value,
                                    serverIndex
                                )
                            }}
                        />
                    </Stack>
                </Box>
            </AccordionDetails>
        </Accordion>
    )
}

export default ServerFormSettings
