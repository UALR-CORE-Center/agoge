// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import React from 'react';
import {afterEach, describe, expect, it} from 'vitest';
import {WorkoutStates} from '../../../types/AgogeStates';
import {WorkoutConnectButton} from './WorkoutConnectButton';

const PARENT_SSH = {display: false, protocol: 'ssh', username: 'instructor', password: 'parent-secret'};
const KALI_RDP = {display: true, protocol: 'rdp', username: 'kali', password: 'kali-pw', alias_index: 0, nested_guest: 'kali', security_mode: 'any'};
const KALI_SSH = {display: true, protocol: 'ssh', username: 'kali', password: 'kali-pw', alias_index: 0, nested_guest: 'kali'};

const nestedHost = (hostname: string | null, human_interaction: object[] = [PARENT_SSH, KALI_SSH]) => ({
    name: 'nestedhost',
    state: WorkoutStates.RUNNING,
    hostname,
    nics: [{network: 'external', ip_aliases: ['10.1.1.2']}],
    human_interaction,
});

const openDialog = (item: object) => {
    render(<WorkoutConnectButton item={item} buildId="abcdefghij" serverIdx="0" addGuacamole={true}/>);
    fireEvent.click(screen.getByRole('button', {name: 'Connect'}));
};

describe('WorkoutConnectButton on a nested host', () => {
    afterEach(cleanup);

    it('shows the jumpbox SSH command on a direct-connect host and never the parent login', () => {
        openDialog(nestedHost('nestedhost.agoge-labs.com'));

        expect(screen.getByText('ssh kali@nestedhost.agoge-labs.com')).toBeInTheDocument();
        expect(screen.getByText('kali-pw')).toBeInTheDocument();
        expect(screen.queryByText(/instructor/)).not.toBeInTheDocument();
        expect(screen.queryByText('parent-secret')).not.toBeInTheDocument();
        expect(screen.getByRole('link', {name: /Guacamole/})).toBeInTheDocument();
    });

    it('falls back to the jumpbox credentials and Guacamole without a direct-connect hostname', () => {
        openDialog(nestedHost(null));

        expect(screen.getByText(/Hostname not available/)).toBeInTheDocument();
        expect(screen.getByText('kali')).toBeInTheDocument();
        expect(screen.queryByText('parent-secret')).not.toBeInTheDocument();
    });

    it('never falls back to the parent login when the host has no guest connections', () => {
        openDialog(nestedHost('nestedhost.agoge-labs.com', [PARENT_SSH]));

        expect(screen.getByText(/No connections are available for this server/)).toBeInTheDocument();
        expect(screen.queryByText(/instructor@/)).not.toBeInTheDocument();
        expect(screen.queryByText('instructor')).not.toBeInTheDocument();
        expect(screen.queryByText('parent-secret')).not.toBeInTheDocument();
    });

    it('still shows every connection of a plain direct-connect server', () => {
        openDialog({
            name: 'kali', state: WorkoutStates.RUNNING, hostname: 'kali.agoge-labs.com',
            nics: [{network: 'external'}], human_interaction: [{protocol: 'ssh', username: 'student', password: 'spw'}],
        });

        expect(screen.getByText('ssh student@kali.agoge-labs.com')).toBeInTheDocument();
    });

    it('tunnels the jumpbox RDP over its direct SSH', () => {
        openDialog(nestedHost('nestedhost.agoge-labs.com', [PARENT_SSH, KALI_SSH, KALI_RDP]));

        expect(screen.getByText('ssh -L 13389:localhost:3389 kali@nestedhost.agoge-labs.com')).toBeInTheDocument();
        expect(screen.getByText('localhost:13389')).toBeInTheDocument();
    });

    it('offers no tunnel for RDP without a direct-connect hostname', () => {
        openDialog(nestedHost(null, [PARENT_SSH, KALI_SSH, KALI_RDP]));

        expect(screen.queryByText(/ssh -L/)).not.toBeInTheDocument();
    });

    it('keeps the plain RDP hostname on a direct-connect server', () => {
        openDialog({
            name: 'win', state: WorkoutStates.RUNNING, hostname: 'win.agoge-labs.com',
            nics: [{network: 'external'}], human_interaction: [{protocol: 'rdp', username: 'student', password: 'spw'}],
        });

        expect(screen.getByText('win.agoge-labs.com')).toBeInTheDocument();
        expect(screen.queryByText(/ssh -L/)).not.toBeInTheDocument();
    });
});

describe('WorkoutConnectButton Guacamole links', () => {
    afterEach(cleanup);

    const jumpbox = {...nestedHost('nested-host.agoge-labs.com', [PARENT_SSH, KALI_SSH, KALI_RDP]), name: 'nested-host'};
    // As DisplayProxy records them: sorted by server, registration order within a server, indexed across the workout
    const proxyConnections = [
        {server: 'attacker', idx: 0, username: 'agoge0'},
        {server: 'nested-host', idx: 1, username: 'agoge1'},
        {server: 'nested-host', idx: 2, username: 'agoge2'},
    ];

    const openWith = (item: object, connections?: object[], serverIdx = '1') => {
        render(<WorkoutConnectButton item={item} buildId="abcdefghij" serverIdx={serverIdx} addGuacamole={true}
                                     proxyConnections={connections as never}/>);
        fireEvent.click(screen.getByRole('button', {name: 'Connect'}));
    };

    it('links each protocol tab of a jumpbox to its own connection index', () => {
        openWith(jumpbox, proxyConnections);

        expect(screen.getByRole('link', {name: /Guacamole SSH/})).toHaveAttribute(
            'href', expect.stringMatching(/\/abcdefghij\/guacamole\/1$/));
        fireEvent.click(screen.getByRole('tab', {name: 'rdp'}));
        expect(screen.getByRole('link', {name: /Guacamole RDP/})).toHaveAttribute(
            'href', expect.stringMatching(/\/abcdefghij\/guacamole\/2$/));
        expect(screen.queryByRole('link', {name: /Guacamole SSH/})).not.toBeInTheDocument();
    });

    it('offers no Guacamole link for a connection the proxy does not carry', () => {
        // A community workout's shared proxy carries only a server's first displayed connection
        openWith(jumpbox, [{server: 'nested-host', idx: 0}]);

        expect(screen.getByRole('link', {name: /Guacamole SSH/})).toHaveAttribute(
            'href', expect.stringMatching(/\/guacamole\/0$/));
        fireEvent.click(screen.getByRole('tab', {name: 'rdp'}));
        expect(screen.queryByRole('link', {name: /Guacamole/})).not.toBeInTheDocument();
    });

    it('falls back to the server index without proxy connection records', () => {
        openWith({
            name: 'kali', state: WorkoutStates.RUNNING, hostname: 'kali.agoge-labs.com',
            nics: [{network: 'external'}], human_interaction: [{protocol: 'ssh', username: 'student', password: 'spw'}],
        }, undefined, '3');

        expect(screen.getByRole('link', {name: /Guacamole/})).toHaveAttribute(
            'href', expect.stringMatching(/\/guacamole\/3$/));
    });
});
