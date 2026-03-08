import { useState, useEffect } from 'react';
import { userService } from "../services/User/user.service";

let sharedUserIp = null;
let ipSubscribers = [];

export function useUserIp() {
    const [userIp, setUserIp] = useState<string>(sharedUserIp);

    useEffect(() => {
        let isMounted = true;

        const fetchUserIp = async () => {
            try {
                const resp = await userService.whoami();
                if (isMounted) {
                    sharedUserIp = resp.requester;
                    setUserIp(sharedUserIp);
                    ipSubscribers.forEach((cb) => cb(sharedUserIp));
                }
            } catch (err) {
                console.error('Error fetching user IP:', err);
            }
        };

        if (sharedUserIp !== null) {
            setUserIp(sharedUserIp);
        } else {
            fetchUserIp();
        }

        const subscriber = (newIp) => setUserIp(newIp);
        ipSubscribers.push(subscriber);

        return () => {
            isMounted = false;
            ipSubscribers = ipSubscribers.filter((cb) => cb !== subscriber);
        };
    }, []);

    return userIp;
}
