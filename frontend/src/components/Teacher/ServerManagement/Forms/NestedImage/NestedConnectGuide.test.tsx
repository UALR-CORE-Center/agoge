// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import React from 'react';
import {afterEach, describe, expect, it} from 'vitest';
import NestedConnectGuide from './NestedConnectGuide';
import {NestedTunnel} from './nestedImageStatus';

const CONSOLE: NestedTunnel = {guest: 'kali', kind: 'console', local_port: 5901, destination: 'localhost:5901',
    command: 'ssh -L 5901:localhost:5901 instructor@lab.example.test'};
const SSH: NestedTunnel = {guest: 'kali', kind: 'ssh', local_port: 2222, destination: '192.168.100.10:22',
    command: 'ssh -L 2222:192.168.100.10:22 instructor@lab.example.test'};
const RDP: NestedTunnel = {guest: 'win', kind: 'rdp', local_port: 13390, destination: '192.168.100.166:3389',
    command: 'ssh -L 13390:192.168.100.166:3389 instructor@lab.example.test'};

const renderGuide = (tunnels: NestedTunnel[]) => {
    render(<NestedConnectGuide tunnels={tunnels} username={'instructor'} hostname={'lab.example.test'}
        guestUsers={{kali: 'kali', win: 'Administrator'}} />);
    fireEvent.click(screen.getByRole('button', {name: /How to connect/}));
};

describe('NestedConnectGuide', () => {
    afterEach(cleanup);

    it('walks through the tunnel and the guest SSH login with this host\'s values on macOS or Linux', () => {
        // jsdom's user agent is not Windows, so the guide opens on macOS / Linux.
        renderGuide([CONSOLE, RDP, SSH]);
        expect(screen.getByRole('button', {name: 'macOS / Linux'})).toHaveAttribute('aria-pressed', 'true');
        // The SSH guest is the example even when a console and RDP come first.
        expect(screen.getByText('ssh -N -L 2222:192.168.100.10:22 instructor@lab.example.test')).toBeInTheDocument();
        expect(screen.getByText('ssh -p 2222 kali@localhost')).toBeInTheDocument();
    });

    it('gives Windows the same OpenSSH commands in PowerShell', () => {
        renderGuide([SSH]);
        fireEvent.click(screen.getByRole('button', {name: 'Windows (PowerShell)'}));
        expect(screen.getByText('ssh -N -L 2222:192.168.100.10:22 instructor@lab.example.test')).toBeInTheDocument();
        expect(screen.getByText('ssh -p 2222 kali@localhost')).toBeInTheDocument();
        expect(screen.getByText(/add OpenSSH Client/)).toBeInTheDocument();
    });

    it('splits the tunnel into PuTTY\'s session and Tunnels fields', () => {
        renderGuide([SSH]);
        fireEvent.click(screen.getByRole('button', {name: 'Windows (PuTTY)'}));
        expect(screen.getByText('instructor@lab.example.test', {selector: 'code'})).toBeInTheDocument();
        expect(screen.getByText('192.168.100.10:22', {selector: 'code'})).toBeInTheDocument();
        // The tunnel's source port, then the port the second PuTTY window connects to.
        expect(screen.getAllByText('2222', {selector: 'code'})).toHaveLength(2);
        expect(screen.getByText(/Log in as/)).toHaveTextContent('Log in as kali');
        expect(screen.queryByText(/ssh -N/)).not.toBeInTheDocument();
    });

    it('opens Remote Desktop with mstsc when the host has only a Windows guest', () => {
        renderGuide([RDP]);
        fireEvent.click(screen.getByRole('button', {name: 'Windows (PowerShell)'}));
        expect(screen.getByText('ssh -N -L 13390:192.168.100.166:3389 instructor@lab.example.test')).toBeInTheDocument();
        expect(screen.getByText('mstsc /v:localhost:13390')).toBeInTheDocument();
    });

    it('says whether a click shows or hides the steps', () => {
        render(<NestedConnectGuide tunnels={[SSH]} username={'instructor'} hostname={'lab.example.test'} guestUsers={{kali: 'kali'}} />);
        const summary = screen.getByRole('button', {name: /How to connect/});
        expect(summary).toHaveAttribute('aria-expanded', 'false');
        expect(summary).toHaveTextContent('Show steps');
        fireEvent.click(summary);
        expect(summary).toHaveAttribute('aria-expanded', 'true');
        expect(summary).toHaveTextContent('Hide steps');
        // The hint is for sighted users; the accessible name stays the same either way.
        expect(screen.getByRole('button', {name: 'How to connect from Windows, macOS, or Linux'})).toBe(summary);
    });

    it('renders nothing without a tunnel', () => {
        render(<NestedConnectGuide tunnels={[]} username={'instructor'} hostname={'lab.example.test'} guestUsers={{}} />);
        expect(screen.queryByText(/How to connect/)).not.toBeInTheDocument();
    });
});
