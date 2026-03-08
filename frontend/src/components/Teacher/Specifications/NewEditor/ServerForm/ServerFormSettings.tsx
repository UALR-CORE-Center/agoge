import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {Accordion, AccordionDetails, AccordionSummary, Box, useTheme} from "@mui/material";
import React from "react";
import {
    FormCheckBox,
    FormRadioBtns,
    StyledFormFieldLabel
} from "../utils/FormFields";
import {ServerFormKeys} from "./ServerFormTypes";
import {IUseServerForm} from "./useServerForm";

interface Props {
    serverForm: IUseServerForm,
    serverIndex: number;
    disableForm: boolean;
    expanded: boolean;
}

const ServerFormSettings: React.FC<Props> = ({serverForm, serverIndex, disableForm, expanded}) => {
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
                </Box>
            </AccordionDetails>
        </Accordion>
    )
}

export default ServerFormSettings