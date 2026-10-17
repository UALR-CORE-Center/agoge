import React from "react";
import {ServerStates} from "../../../types/AgogeStates";
import NestedTunnelHints from "../../Teacher/ServerManagement/Forms/NestedImage/NestedTunnelHints";
import {BaseConnectButton, ConnectButtonProps} from "./BaseConnectButton";
import {CustomTabPanel} from "./CustomTabPanel";

export const ServerConnectButton: React.FC<ConnectButtonProps> = ({ item }) => {
    const parsedHumanInteraction = item?.human_interaction[0] || "";
    const protocol = parsedHumanInteraction.protocol;
    const fullInteractions = (item.human_interaction) || [];

    const [selectedProtocol, setSelectedProtocol] = React.useState<string>(protocol);

    const handleProtocolChange = (event: React.SyntheticEvent, newValue: string) => {
        setSelectedProtocol(newValue);
    }

    const isDisabled = () => item.state === ServerStates.START || item.state !== ServerStates.RUNNING;

    const renderDetails = (item: any) => {
        // The parent's SSH access (human_interaction) is the tunnel endpoint for nested guests.
        const parentSsh = fullInteractions.find((interaction: any) => interaction.protocol === "ssh");
        return (
            <>
                <CustomTabPanel
                    key={item.name}
                    item={item}
                    fullInteractions={fullInteractions}
                    selectedProtocol={selectedProtocol}
                    handleProtocolChange={handleProtocolChange}
                    parsedHumanInteraction={parsedHumanInteraction}
                />
                {item.nested && (
                    <NestedTunnelHints
                        spec={item.nested}
                        hostname={item.dns_record || item.hostname}
                        username={parentSsh?.username}
                    />
                )}
            </>
        );
    };

    return <BaseConnectButton item={item} isDisabled={isDisabled} renderDetails={renderDetails} />;
};