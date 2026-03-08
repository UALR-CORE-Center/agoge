import {IServerForm, ServerFormKeys} from "./ServerFormTypes";
import React from "react";
import {Accordion, AccordionDetails, AccordionSummary, Button, Stack, Typography, useTheme} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {FormFields, StyledFormFieldLabel} from "../utils/FormFields";
import {Add, ErrorOutline} from "@mui/icons-material";
import {Network} from "../../../../../services/Specification/specification.model";
import ServerFormNic from "./ServerFormNic";
import {IUseServerForm} from "./useServerForm";

interface Props {
    server: IServerForm
    serverForm: IUseServerForm,
    serverIndex: number;
    remoteNetworkInterfaces: Network[];
    localNetworkInterfaces: string[];
    disableForm: boolean;
}

const ServerFormNetwork: React.FC<Props> = ({
                                                server,
                                                disableForm,
                                                serverForm,
                                                serverIndex,
                                                remoteNetworkInterfaces,
                                                localNetworkInterfaces
                                            }) => {
    const theme = useTheme();
    return (
        <Accordion defaultExpanded={true} elevation={3}>
            <AccordionSummary expandIcon={<ExpandMoreIcon/>}
                              sx={{background: theme.palette.action.hover}}>
                <Stack gap={1} direction={'row'} alignItems={'center'}>
                    <StyledFormFieldLabel>Network Interface</StyledFormFieldLabel>
                    <Typography
                        color={'text.secondary'}>({server[ServerFormKeys.serverNetworks].length} NICs)</Typography>
                    {
                        serverForm.doesServerNetworkHaveErrors(serverIndex) &&
                        <ErrorOutline fontSize={'small'} color={'error'}/>
                    }
                </Stack>
            </AccordionSummary>
            <AccordionDetails>

                <FormFields gap={.5}>
                    {
                        server[ServerFormKeys.serverNetworks].map((nicForm, nicIdx) =>
                            <ServerFormNic
                                key={nicIdx}
                                serverIndex={serverIndex}
                                disableForm={disableForm}
                                serverForm={serverForm}
                                nic={nicForm}
                                nicIndex={nicIdx}
                                localNetworkInterfaces={localNetworkInterfaces}
                                remoteNetworkInterfaces={remoteNetworkInterfaces}
                            />
                        )
                    }


                    <Button onClick={() => serverForm.addNic(serverIndex)}
                            disabled={remoteNetworkInterfaces.length == server[ServerFormKeys.serverNetworks].length || disableForm}
                            sx={{width: '30%', minWidth: '150px', mx: 'auto', mt: theme.spacing(2)}}
                            variant={'contained'} color={'primary'} endIcon={<Add/>}>Add NIC</Button>
                </FormFields>

            </AccordionDetails>
        </Accordion>

    )
}

export default ServerFormNetwork;
