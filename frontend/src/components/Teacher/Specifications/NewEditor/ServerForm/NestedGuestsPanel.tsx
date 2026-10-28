import {Cable, Lan} from "@mui/icons-material";
import {
    Alert,
    Button,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    Typography,
} from "@mui/material";
import React, {useEffect, useState} from "react";

import {NestedOsCatalogEntry} from "../../../../../services/Server/nested.model";
import {nestedService} from "../../../../../services/Server/nested.service";
import {Network} from "../../../../../services/Specification/specification.model";
import {FormGroup, FormGroupOutline, StyledFormFieldLabel} from "../utils/FormFields";
import {ServerFormKeys} from "./ServerFormTypes";
import {
    fillAliasIps,
    mergeNestedConnections,
    NestedImage,
    nestedConnections,
    networkCidr,
    splitAliases,
} from "./nestedServer";
import {IUseServerForm} from "./useServerForm";

interface Props {
    image: NestedImage;
    serverForm: IUseServerForm;
    serverIndex: number;
    networks: Network[];
    disableForm: boolean;
}

// Every address on `network` other than this server's NIC 0 aliases, which are the ones being refilled
const takenAddresses = (serverForm: IUseServerForm, serverIndex: number, network: string, reserved: string[]): string[] =>
    serverForm.forms.flatMap((form, formIndex) =>
        form[ServerFormKeys.serverNetworks].flatMap((nic, nicIndex) => {
            if (nic[ServerFormKeys.serverNicNetwork].value !== network) {
                return [];
            }
            const ip = nic[ServerFormKeys.serverNicIPv4Addr].value;
            const aliases = formIndex === serverIndex && nicIndex === 0
                ? []
                : splitAliases(nic[ServerFormKeys.serverNicIpAliases].value);
            return [...(ip ? [String(ip)] : []), ...aliases];
        })
    ).concat(reserved);

const NestedGuestsPanel: React.FC<Props> = ({image, serverForm, serverIndex, networks, disableForm}) => {
    const [catalog, setCatalog] = useState<NestedOsCatalogEntry[]>([]);
    const [message, setMessage] = useState<{ severity: 'success' | 'error', text: string } | null>(null);

    useEffect(() => {
        nestedService.list_catalog().then(setCatalog).catch(() => setCatalog([]));
    }, []);

    const nested = image.nested;
    const form = serverForm.forms[serverIndex];
    const nic0 = form?.[ServerFormKeys.serverNetworks][0];
    const aliases = nic0 ? splitAliases(nic0[ServerFormKeys.serverNicIpAliases].value) : [];
    const slotCount = nested.exposures.length;

    const fillAliases = () => {
        if (!nic0 || !nic0[ServerFormKeys.serverNicNetwork].value) {
            setMessage({severity: 'error', text: 'Add NIC 0 and choose its network first.'});
            return;
        }
        const network = nic0[ServerFormKeys.serverNicNetwork].value;
        const reserved = networks.find(item => item.name === network)?.reservations || [];
        const filled = fillAliasIps(
            networkCidr(networks, network),
            slotCount,
            aliases,
            takenAddresses(serverForm, serverIndex, network, reserved),
        );
        if (!filled) {
            setMessage({
                severity: 'error',
                text: `Could not find ${slotCount} free address(es) in network ${network}. Save the Networks step so its subnet is known, or enter the aliases by hand.`,
            });
            return;
        }
        serverForm.handleNicValueChange(ServerFormKeys.serverNicIpAliases, filled.join(','), serverIndex, 0);
        setMessage({severity: 'success', text: `NIC 0 aliases set to ${filled.join(', ') || 'none'}.`});
    };

    const addConnections = () => {
        const current = form?.[ServerFormKeys.serverHumanInteraction]?.value ?? image.human_interaction ?? [];
        const generated = nestedConnections(nested, catalog);
        serverForm.handleServerValueChange(
            ServerFormKeys.serverHumanInteraction, mergeNestedConnections(current, generated), serverIndex,
        );
        setMessage({severity: 'success', text: `Added ${generated.length} guest connection(s).`});
    };

    return (
        <FormGroupOutline showOverlay={disableForm}>
            <FormGroup>
                <StyledFormFieldLabel>Nested guests</StyledFormFieldLabel>
                <Typography variant="body2" color="text.secondary">
                    This image is a nested lab host. Exposed guest <i>n</i> answers on NIC 0 alias <i>n</i>, so NIC 0
                    needs {slotCount} alias IP(s), and the server needs an N1, N2, or N4 machine type. Students reach only
                    exposed guests. To let them SSH straight to the first exposed Linux guest (the jumpbox), enable
                    External NAT and Direct Connections on NIC 0.
                </Typography>
                <Table size="small" aria-label="Nested guests">
                    <TableHead>
                        <TableRow>
                            <TableCell>Guest</TableCell>
                            <TableCell>OS</TableCell>
                            <TableCell>Alias slot</TableCell>
                            <TableCell>Console port</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {nested.guests.map(guest => {
                            const slot = nested.exposures.findIndex(([name]) => name === guest.name);
                            return (
                                <TableRow key={guest.name}>
                                    <TableCell>{guest.name}</TableCell>
                                    <TableCell>
                                        {catalog.find(entry => entry.id === guest.os_id)?.display_name ?? guest.os_id}
                                    </TableCell>
                                    <TableCell>
                                        {slot < 0 ? '—' : `${slot} (${aliases[slot] ?? 'no alias'})`}
                                    </TableCell>
                                    <TableCell>{nested.console_ports[guest.name] ?? '—'}</TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
                <Stack direction={{xs: 'column', sm: 'row'}} gap={1} mt={1}>
                    <Button variant="outlined" startIcon={<Lan/>} disabled={disableForm} onClick={fillAliases}>
                        Fill alias IPs
                    </Button>
                    <Button variant="outlined" startIcon={<Cable/>} disabled={disableForm} onClick={addConnections}>
                        Add connections
                    </Button>
                </Stack>
                {message && <Alert severity={message.severity} sx={{mt: 1}}>{message.text}</Alert>}
            </FormGroup>
        </FormGroupOutline>
    );
};

export default NestedGuestsPanel;
