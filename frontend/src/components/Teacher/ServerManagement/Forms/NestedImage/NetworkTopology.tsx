import {Box, useTheme} from "@mui/material";
import React, {useId} from "react";
import {NestedGuest, NestedNetwork} from "../../../../../services/Server/nested.model";

// Read-only picture of the lab: networks are horizontal rails, the parent and each guest are boxes above them,
// and a drop line joins a box to every rail it has an address or NIC on. Inline SVG, no chart library.
const LABEL_WIDTH = 190;
const BOX_WIDTH = 120;
const BOX_HEIGHT = 44;
const BOX_GAP = 24;
const TOP = 12;
const FIRST_RAIL = TOP + BOX_HEIGHT + 40;
const RAIL_GAP = 52;

interface NetworkTopologyProps {
    networks: NestedNetwork[];
    guests: NestedGuest[];
}

interface Drop {
    railIndex: number;
    label: string;
}

const truncate = (text: string, length: number): string =>
    text.length > length ? `${text.slice(0, length - 1)}…` : text;

const NetworkTopology: React.FC<NetworkTopologyProps> = ({networks, guests}) => {
    const theme = useTheme();
    const titleId = useId();
    const railIndex = (name: string) => networks.findIndex(network => network.name === name);

    const parentDrops: Drop[] = networks.flatMap((network, index) =>
        network.parent_address ? [{railIndex: index, label: network.parent_address}] : []);
    const nodes: {name: string; detail: string; drops: Drop[]}[] = [
        {name: "parent", detail: "libvirt host", drops: parentDrops},
        ...guests.map(guest => ({
            name: guest.name || "unnamed",
            detail: guest.os_id,
            // A NIC on a network that no longer exists has no rail to drop to; the Guests step reports it.
            drops: guest.nics
                .map(nic => ({railIndex: railIndex(nic.network), label: nic.ip || "DHCP"}))
                .filter(drop => drop.railIndex >= 0),
        })),
    ];

    const width = LABEL_WIDTH + nodes.length * (BOX_WIDTH + BOX_GAP);
    const railY = (index: number) => FIRST_RAIL + index * RAIL_GAP;
    const height = railY(Math.max(networks.length, 1) - 1) + 24;
    const line = theme.palette.text.secondary;
    const accent = theme.palette.primary.main;
    const description = `${networks.length} network(s), ${guests.length} guest(s)`;

    return (
        <Box sx={{overflowX: "auto", border: 1, borderColor: "divider", borderRadius: 1, p: 1}}>
            <svg
                role="img"
                aria-labelledby={titleId}
                width={width}
                height={height}
                viewBox={`0 0 ${width} ${height}`}
                fontFamily={theme.typography.fontFamily}
                fontSize={12}
            >
                <title id={titleId}>{`Network topology: ${description}`}</title>
                {networks.map((network, index) => (
                    <g key={`rail-${index}`} data-testid="topology-rail">
                        <line
                            x1={0}
                            x2={width}
                            y1={railY(index)}
                            y2={railY(index)}
                            stroke={network.mode === "nat" ? accent : line}
                            strokeWidth={3}
                        />
                        <text x={4} y={railY(index) - 18} fill={theme.palette.text.primary} fontWeight={600}>
                            {truncate(network.name || `network ${index + 1}`, 24)}
                        </text>
                        <text x={4} y={railY(index) - 5} fill={line}>
                            {`${network.cidr} · ${network.mode === "nat" ? "NAT" : "isolated"}`}
                        </text>
                    </g>
                ))}
                {nodes.map((node, nodeIndex) => {
                    const x = LABEL_WIDTH + nodeIndex * (BOX_WIDTH + BOX_GAP);
                    const centre = x + BOX_WIDTH / 2;
                    return (
                        <g key={`node-${nodeIndex}`} data-testid="topology-node">
                            {node.drops.map((drop, dropIndex) => (
                                <g key={`drop-${dropIndex}`}>
                                    <line
                                        x1={centre}
                                        x2={centre}
                                        y1={TOP + BOX_HEIGHT}
                                        y2={railY(drop.railIndex)}
                                        stroke={line}
                                        strokeWidth={1.5}
                                    />
                                    <circle cx={centre} cy={railY(drop.railIndex)} r={4} fill={line} />
                                    <text x={centre + 6} y={railY(drop.railIndex) - 5} fill={line} fontSize={11}>
                                        {drop.label}
                                    </text>
                                </g>
                            ))}
                            <rect
                                x={x}
                                y={TOP}
                                width={BOX_WIDTH}
                                height={BOX_HEIGHT}
                                rx={6}
                                fill={theme.palette.background.paper}
                                stroke={nodeIndex === 0 ? accent : line}
                                strokeWidth={1.5}
                            />
                            <text x={centre} y={TOP + 18} textAnchor="middle" fill={theme.palette.text.primary} fontWeight={600}>
                                {truncate(node.name, 16)}
                            </text>
                            <text x={centre} y={TOP + 34} textAnchor="middle" fill={line} fontSize={11}>
                                {truncate(node.detail, 18)}
                            </text>
                        </g>
                    );
                })}
            </svg>
        </Box>
    );
};

export default NetworkTopology;
