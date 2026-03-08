import React from "react";
import {ServerStates} from "../../../types/AgogeStates";
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
        return (
            <CustomTabPanel
                key={item.name}
                item={item}
                fullInteractions={fullInteractions}
                selectedProtocol={selectedProtocol}
                handleProtocolChange={handleProtocolChange}
                parsedHumanInteraction={parsedHumanInteraction}
            />
        );
    };

    return <BaseConnectButton item={item} isDisabled={isDisabled} renderDetails={renderDetails} />;
};