// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import React from "react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {nestedService} from "../../../../../services/Server/nested.service";
import NestedGuestsPanel from "./NestedGuestsPanel";
import {IServerForm, ServerFormKeys} from "./ServerFormTypes";
import {NestedImage} from "./nestedServer";
import {IUseServerForm} from "./useServerForm";

vi.mock("../../../../../services/Server/nested.service", () => ({
    nestedService: {list_catalog: vi.fn()},
}));

const field = (value: unknown) => ({value, error: null, initialized: true, validators: []});

const serverFormWith = (aliases: string, otherIp: string) => {
    const nic = (ip: string, ipAliases: string) => ({
        [ServerFormKeys.serverNicNetwork]: field('lan'),
        [ServerFormKeys.serverNicIPv4Addr]: field(ip),
        [ServerFormKeys.serverNicIpAliases]: field(ipAliases),
    });
    const forms = [
        {[ServerFormKeys.serverHumanInteraction]: field(null), [ServerFormKeys.serverNetworks]: [nic('10.1.1.10', aliases)]},
        {[ServerFormKeys.serverHumanInteraction]: field(null), [ServerFormKeys.serverNetworks]: [nic(otherIp, '')]},
    ] as unknown as IServerForm[];
    return {forms, handleNicValueChange: vi.fn(), handleServerValueChange: vi.fn()} as unknown as IUseServerForm;
};

const IMAGE = {
    image: 'image-hv',
    human_interaction: [{protocol: 'ssh', username: 'root'}],
    nested: {
        guests: [
            {name: 'dc', os_id: 'win2019', admin_username: 'admin', admin_password: 'pw', console: true},
            {name: 'kali', os_id: 'kali', admin_username: 'kali', admin_password: 'kpw', console: true},
        ],
        exposures: [['dc', 0]],
        console_ports: {dc: 5901, kali: 5902},
        vnc_passwords: {dc: 'vncdc001', kali: 'vncka001'},
    },
} as unknown as NestedImage;

const NETWORKS = [{name: 'lan', subnets: [{name: 'default', ip_subnet: '10.1.1.0/24'}]}];

describe('NestedGuestsPanel', () => {
    afterEach(cleanup);

    it('fills NIC 0 aliases with free addresses and adds the guest connections', async () => {
        vi.mocked(nestedService.list_catalog).mockResolvedValue([
            {id: 'win2019', display_name: 'Windows Server 2019', family: 'windows', agent: true},
        ] as never);
        // .2 is the other server's address, so slot 0 takes .3
        const serverForm = serverFormWith('', '10.1.1.2');
        render(<NestedGuestsPanel image={IMAGE} serverForm={serverForm} serverIndex={0} networks={NETWORKS} disableForm={false}/>);

        expect(await screen.findByText('Windows Server 2019')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', {name: 'Fill alias IPs'}));
        expect(serverForm.handleNicValueChange).toHaveBeenCalledWith(ServerFormKeys.serverNicIpAliases, '10.1.1.3', 0, 0);

        fireEvent.click(screen.getByRole('button', {name: 'Add connections'}));
        await waitFor(() => expect(serverForm.handleServerValueChange).toHaveBeenCalled());
        expect(serverForm.handleServerValueChange).toHaveBeenCalledWith(ServerFormKeys.serverHumanInteraction, [
            {protocol: 'ssh', username: 'root'},
            {protocol: 'rdp', username: 'admin', password: 'pw', alias_index: 0, nested_guest: 'dc'},
            {protocol: 'vnc', password: 'vncka001', port: 5902, nested_guest: 'kali'},
        ], 0);
    });

    it('reports an unknown subnet instead of writing aliases', async () => {
        vi.mocked(nestedService.list_catalog).mockResolvedValue([]);
        const serverForm = serverFormWith('', '10.1.1.2');
        render(<NestedGuestsPanel image={IMAGE} serverForm={serverForm} serverIndex={0} networks={[]} disableForm={false}/>);

        fireEvent.click(screen.getByRole('button', {name: 'Fill alias IPs'}));
        expect(await screen.findByText(/Could not find 1 free address/)).toBeInTheDocument();
        expect(serverForm.handleNicValueChange).not.toHaveBeenCalled();
    });
});
