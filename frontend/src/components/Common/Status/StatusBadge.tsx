import * as React from 'react';
import Chip, { ChipProps } from '@mui/material/Chip';
import { SxProps, Theme } from '@mui/system';

type ChipColor = ChipProps['color'];

interface StatusBadgeProps extends Omit<ChipProps, 'color' | 'label'> {
    color?: ChipColor;
    label: string;
    sx?: SxProps<Theme>;
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ color = 'default', label, sx, ...rest }) => {
    return (
        <Chip
            label={label}
            color={color}
            variant="filled"
            sx={{
                minWidth: 75,
                textAlign: 'center',
                fontSize: '0.75rem',
                lineHeight: 1.5,
                height: 24,
                ...sx,
            }}
            {...rest}
        />
    );
};

export default StatusBadge;