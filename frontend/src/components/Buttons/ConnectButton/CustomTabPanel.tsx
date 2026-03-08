import {Box, Divider, Tab, Tabs, Typography} from "@mui/material";
import React from "react";
import {HumanInteraction} from "../../../services/Specification/specification.model";
import {ConnectButtonProps} from "./BaseConnectButton";
import {UserDetailField} from "./UserDetailField";

interface Props extends ConnectButtonProps {
    selectedProtocol: string;
    handleProtocolChange: (event: React.SyntheticEvent, newValue: string) => void;
    fullInteractions: HumanInteraction[];
    parsedHumanInteraction: HumanInteraction;
    renderGuacamoleConnect?: () => React.ReactNode;
}

export const a11yProps = (protocol: string) => ({
    id: `simple-tab-${protocol}`,
    "aria-controls": `simple-tabpanel-${protocol}`,
});

const TabPanel: React.FC<{
    protocol: string;
    selected: string;
    children: React.ReactNode;
}> = ({ protocol, selected, children }) => {
    const hidden = selected !== protocol;
    return (
        <Box
            role="tabpanel"
            id={`simple-tabpanel-${protocol}`}
            aria-labelledby={`simple-tab-${protocol}`}
            hidden={hidden}
            sx={{ pt: 2, display: hidden ? 'none' : 'block' }}
        >
            {children}
        </Box>
    );
};

export const CustomTabPanel: React.FC<Props> = (props) => {
    const { item, fullInteractions, selectedProtocol, handleProtocolChange, renderGuacamoleConnect } = props;
    const hostname = item.dns_record || item.hostname;

    return (
        <Box sx={{ maxHeight: "70vh", overflowY: "auto", p: 2 }}>
            <Tabs
                key={item.protocol}
                value={selectedProtocol}
                onChange={handleProtocolChange}
                aria-label="Connection methods"
            >
                {fullInteractions.map((interaction, index) => (
                    <Tab
                        key={`${interaction.protocol}-${index}`}
                        label={interaction.protocol}
                        value={interaction.protocol}
                        {...a11yProps(interaction.protocol)}
                        // Removed custom focus-visible styling. MUI handles this by default.
                    />
                ))}
            </Tabs>

            {fullInteractions.map((interaction, index) => (
                <TabPanel
                    key={`panel-${interaction.protocol}-${index}`}
                    protocol={interaction.protocol}
                    selected={selectedProtocol}
                >
                    {interaction.protocol === "rdp" && (
                        <>
                            <Typography
                                id="rdp-connect-modal-description"
                                variant="h6"
                                component="h3"
                                sx={{ mt: 2 }}
                            >
                                RDP
                            </Typography>
                            <Typography sx={{ mt: 2 }}>
                                To connect to this server, connect using your system&#39;s RDP app with the server
                                details provided below.
                            </Typography>
                            <Box sx={{ mt: 2 }}>
                                <ul>
                                    <li>On Windows, this is Remote Desktop Connection</li>
                                    <li>On Mac, it is Microsoft Remote Desktop.</li>
                                </ul>
                            </Box>
                            <Divider />
                            <Box component="section" paddingTop={1}>
                                <UserDetailField label="Hostname" value={String(hostname ?? "")} />
                                <UserDetailField label="Username" value={String(interaction.username ?? "")} />
                                <UserDetailField label="Password" value={String(interaction.password ?? "")} />
                            </Box>
                        </>
                    )}

                    {/* FIX APPLIED HERE: Improved SSH display logic */}
                    {interaction.protocol === "ssh" && (
                        <>
                            <Typography
                                id="ssh-connect-modal-description"
                                variant="h6"
                                component="h3"
                                sx={{ mt: 2 }}
                            >
                                SSH
                            </Typography>
                            <Typography sx={{ mt: 2, mb: 2 }}>
                                On your machine, open up a terminal/command prompt and run the following command and
                                enter the password listed below when prompted.
                            </Typography>
                            <Divider />
                            {hostname ? (
                                <>
                                    <UserDetailField
                                        // Corrected label for SSH command
                                        label="SSH Command"
                                        value={`ssh ${String(interaction.username ?? "")}@${String(hostname)}`}
                                    />
                                    <UserDetailField
                                        label="User Password"
                                        value={String(interaction.password ?? "")}
                                    />
                                </>
                            ) : (
                                // Fallback for when hostname is not available
                                <Box component="section" paddingTop={1}>
                                    <Typography variant="body2" color="error" sx={{mb: 2}}>
                                        Hostname not available. Connect using the credentials below.
                                    </Typography>
                                    <UserDetailField label="Username" value={String(interaction.username ?? "")} />
                                    <UserDetailField label="User Password" value={String(interaction.password ?? "")} />
                                </Box>
                            )}
                        </>
                    )}
                </TabPanel>
            ))}

            {renderGuacamoleConnect && renderGuacamoleConnect()}
        </Box>
    );
};