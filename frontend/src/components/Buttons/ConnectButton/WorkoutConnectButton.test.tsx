// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import React from 'react';
import {afterEach, describe, expect, it} from 'vitest';
import {WorkoutStates} from '../../../types/AgogeStates';
import {WorkoutConnectButton} from './WorkoutConnectButton';

const PARENT_SSH = {display: false, protocol: 'ssh', username: 'instructor', password: 'parent-secret'};
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
});
