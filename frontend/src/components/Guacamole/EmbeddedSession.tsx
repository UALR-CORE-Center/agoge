import React, { useEffect, useRef, useState } from 'react';
import { Box } from "@mui/material";
import Guacamole from "guacamole-common-js";
import { useParams } from "react-router-dom";

import { guacamoleService } from '../../services/Guacamole/guacamole.service';
import { GuacamoleSessionType } from '../../services/Guacamole/guacamole.model';

const GuacamoleSession: React.FC = () => {
    const { buildId, serverIdx } = useParams<{ buildId: string; serverIdx: string }>();
    const [session, setSession] = useState<GuacamoleSessionType | null>(null);
    const guacamoleContainer = useRef<HTMLDivElement>(null);
    const hasFetchedToken = useRef(false); // Ref to track if the request has been made

    useEffect(() => {
        const fetchSession = async () => {
            if (hasFetchedToken.current) return; // Prevent double request
            hasFetchedToken.current = true;

            try {
                const session = await guacamoleService.getSession(buildId, serverIdx);
                console.log("Fetched Session:", session);
                setSession(session);
            } catch (error) {
                if (error instanceof Error) {
                    console.error("Error fetching session:", error.message);
                } else {
                    console.error("An unknown error occurred");
                }
            }
        };

        fetchSession();
    }, [buildId, serverIdx]);

    useEffect(() => {
        if (session && guacamoleContainer.current) {
            // Capture the current value of the ref
            const container = guacamoleContainer.current;
            const endpoint = guacamoleService.tokenizedUrl(session);

            if (endpoint.includes('#') || endpoint.includes('?undefined')) {
                console.error("Invalid WebSocket URL:", endpoint);
                return;
            }

            try {
                const tunnel = new Guacamole.WebSocketTunnel(endpoint);
                const guacamoleClient = new Guacamole.Client(tunnel);

                guacamoleClient.onerror = (status) => {
                    console.error("Guacamole Client Error:", status);
                };

                guacamoleClient.onstatechange = (state) => {
                    console.log("Guacamole Client State:", state);
                };

                container.appendChild(guacamoleClient.getDisplay().getElement());

                guacamoleClient.connect();

                // Set z-index for canvas elements
                const element = guacamoleClient.getDisplay().getElement();
                const canvases = element.getElementsByTagName('canvas');
                for (let canvas of canvases) {
                    canvas.style.zIndex = '10';
                }

                const resizeHandler = () => {
                    const display = guacamoleClient.getDisplay();
                    const scale = Math.min(
                        container.offsetWidth / display.getWidth(),
                        container.offsetHeight / display.getHeight()
                    );
                    display.scale(scale);
                };

                window.addEventListener('resize', resizeHandler);
                // Initial call to set the correct scale
                resizeHandler();

                return () => {
                    guacamoleClient.disconnect();
                    if (container) {
                        container.innerHTML = '';
                    }
                    window.removeEventListener('resize', resizeHandler);
                };
            } catch (error) {
                console.error("Error initializing Guacamole WebSocketTunnel:", error);
            }
        }
    }, [session]);

    return (
        <Box ref={guacamoleContainer}
             className="guac-container"
             sx={{ width: '100%', height: '100%', position: 'relative' }}
        >
            {session ? null : <p>Loading...</p>}
        </Box>
    );
};

export default GuacamoleSession;
