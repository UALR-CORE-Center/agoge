import {OpenInBrowser} from "@mui/icons-material";
import {
    Box, Button,
    Divider,
    Typography
} from "@mui/material";
import React, {useState} from "react";
import {URL_STUDENT_WORKOUT} from "../../../router/urls";
import {HumanInteraction} from "../../../services/Specification/specification.model";
import {WorkoutStates} from "../../../types/AgogeStates";
import {absoluteUrl} from "../../../utilities/appContext";
import {studentConnections} from "../../Teacher/Specifications/NewEditor/ServerForm/nestedServer";
import {BaseConnectButton, ConnectButtonProps} from "./BaseConnectButton";
import {CustomTabPanel} from "./CustomTabPanel";


/**
 * The Guacamole index of each of the server's connections. DisplayProxy (and a community workout's shared proxy)
 * records one proxy connection per proxied interaction, server by server in registration order, so the server's
 * Nth proxy connection is its Nth displayed interaction. Without proxy connection records (an older workout) every
 * connection falls back to the server index the table assigns.
 */
const guacamoleIndexes = (
    item: any,
    proxyConnections: ConnectButtonProps['proxyConnections'],
    serverIdx: string | undefined,
): Map<HumanInteraction, string> => {
    const indexes = new Map<HumanInteraction, string>();
    const interactions: HumanInteraction[] = item.human_interaction ?? [];
    if (!proxyConnections?.length) {
        if (serverIdx) {
            interactions.forEach(interaction => indexes.set(interaction, serverIdx));
        }
        return indexes;
    }
    const ofServer = proxyConnections
        .filter(connection => connection.server === item.name && connection.idx != null)
        .sort((a, b) => Number(a.idx) - Number(b.idx));
    interactions
        .filter(interaction => interaction.display)
        .forEach((interaction, position) => {
            if (position < ofServer.length) {
                indexes.set(interaction, String(ofServer[position].idx));
            }
        });
    return indexes;
};

export const WorkoutConnectButton: React.FC<ConnectButtonProps> = (props) => {
    const fullInteractions = studentConnections(
        props.item.human_interaction,
        !!props.item.nics?.[0]?.ip_aliases?.length,
    );
    const parsedHumanInteraction = fullInteractions[0];
    const protocol = parsedHumanInteraction?.protocol ?? "";
    const isDisabled = () => props.item.state !== WorkoutStates.RUNNING;

    const [selectedProtocol, setSelectedProtocol] = useState<string>(protocol);

    const indexes = guacamoleIndexes(props.item, props.proxyConnections, props.serverIdx);

    const renderGuacamoleConnect = (interaction: HumanInteraction) => {
        const index = indexes.get(interaction);
        if (!props.addGuacamole || !props.buildId || index === undefined) {
            return null;
        }
        const label = String(interaction.protocol ?? "").toUpperCase();
        return (
            <>
                <Divider sx={{my: 2}} />
                <Box>
                    <Typography variant={"h5"} component="h3" sx={{my: 1}}>Alternative Connection Method</Typography>
                    <Typography variant={"body1"} my={1}>
                        If you are unable to use {label} on your machine,
                        you can connect via Guacamole here:
                    </Typography>
                    <Button
                        variant={"contained"}
                        color={"success"}
                        href={absoluteUrl(`${URL_STUDENT_WORKOUT}/${props.buildId}/guacamole/${index}`)}
                        target={"_blank"}
                        endIcon={<OpenInBrowser />}
                        aria-label={`Link to Guacamole ${label} session`}
                    >
                        Connect with Guacamole
                    </Button>
                </Box>
            </>
        );
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