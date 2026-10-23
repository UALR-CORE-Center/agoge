// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import React from 'react';
import {afterEach, describe, expect, it} from 'vitest';
import {BaseConnectButton} from './BaseConnectButton';

const openDialog = () => {
    render(<BaseConnectButton item={{name: 'lab'}} isDisabled={() => false} renderDetails={() => <p>ssh -L 2222:10.0.0.5:22 me@lab</p>}/>);
    fireEvent.click(screen.getByRole('button', {name: 'Connect'}));
};

describe('BaseConnectButton', () => {
    afterEach(cleanup);

    it('closes on a click beside the dialog', async () => {
        openDialog();
        const outside = screen.getByTestId('connect-modal-outside');
        fireEvent.mouseDown(outside);
        fireEvent.mouseUp(outside);
        fireEvent.click(outside);
        await waitFor(() => expect(screen.queryByText('Connect to lab')).not.toBeInTheDocument());
    });

    it('stays open when a press inside the dialog is released beside it', () => {
        // Selecting a command and dragging past the Paper's edge fires click on the shared ancestor.
        openDialog();
        const outside = screen.getByTestId('connect-modal-outside');
        fireEvent.mouseDown(screen.getByText('ssh -L 2222:10.0.0.5:22 me@lab'));
        fireEvent.mouseUp(outside);
        fireEvent.click(outside);
        expect(screen.getByText('Connect to lab')).toBeInTheDocument();
    });

    it('stays open when a press beside the dialog is released inside it', () => {
        openDialog();
        const outside = screen.getByTestId('connect-modal-outside');
        fireEvent.mouseDown(outside);
        fireEvent.mouseUp(screen.getByText('ssh -L 2222:10.0.0.5:22 me@lab'));
        fireEvent.click(outside);
        expect(screen.getByText('Connect to lab')).toBeInTheDocument();
    });

    it('stays open on a click inside the dialog', () => {
        openDialog();
        const details = screen.getByText('ssh -L 2222:10.0.0.5:22 me@lab');
        fireEvent.mouseDown(details);
        fireEvent.mouseUp(details);
        fireEvent.click(details);
        expect(screen.getByText('Connect to lab')).toBeInTheDocument();
    });
});
