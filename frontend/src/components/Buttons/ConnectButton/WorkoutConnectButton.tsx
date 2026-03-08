import {OpenInBrowser} from "@mui/icons-material";
import {
    Box, Button,
    Divider,
    Typography
} from "@mui/material";
import React, {useState} from "react";
import {URL_STUDENT_WORKOUT} from "../../../router/urls";
import {WorkoutStates} from "../../../types/AgogeStates";
import {BaseConnectButton, ConnectButtonProps} from "./BaseConnectButton";
import {CustomTabPanel} from "./CustomTabPanel";
import {absoluteUrl} from "../../../utilities/appContext";


export const WorkoutConnectButton: React.FC<ConnectButtonProps> = (props) => {
    const parsedHumanInteraction = (props.item.human_interaction)[0];
    const fullInteractions = (props.item.human_interaction) || [];
    const protocol = parsedHumanInteraction.protocol;
    const isDisabled = () => props.item.state !== WorkoutStates.RUNNING;

    const [selectedProtocol, setSelectedProtocol] = useState<string>(protocol);

    const renderGuacamoleConnect = () => {
        if (props.addGuacamole && props.buildId && props.serverIdx) {
            return (
                <>
                    <Divider sx={{my: 2}} />
                    <Box>
                        <Typography variant={"h5"} component="h3" sx={{my: 1}}>Alternative Connection Method</Typography>
                        <Typography variant={"body1"} my={1}>
                           If you are unable to use {protocol.toUpperCase()} on your machine,
                            you can connect via Guacamole here:
                        </Typography>
                        {/* disable button until guacamole server is created. */}
                        <Button
                            // disabled
                            variant={"contained"}
                            color={"success"}
                            href={absoluteUrl(
                                `${URL_STUDENT_WORKOUT}/${props.buildId}/guacamole/${props.serverIdx}`
                            )}
                            target={"_blank"}
                            endIcon={<OpenInBrowser />}
                            aria-label={"Link to Guacamole server session"}
                        >
                            Connect with Guacamole
                        </Button>
                    </Box>
                </>
            );
        } else {
            return null;
        }
    }

    const handleProtocolChange = (event: React.SyntheticEvent, newValue: string) => {
        setSelectedProtocol(newValue);
    }


    const renderDetails = (item: any) => {
        return (
            <CustomTabPanel
                item={item}
                fullInteractions={fullInteractions}
                selectedProtocol={selectedProtocol}
                handleProtocolChange={handleProtocolChange}
                parsedHumanInteraction={parsedHumanInteraction}
                renderGuacamoleConnect={renderGuacamoleConnect}
            />
        );
    };

    return <BaseConnectButton item={props.item} isDisabled={isDisabled} renderDetails={renderDetails} />;
};