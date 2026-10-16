import {useEffect, useState} from "react";
import {useAuthContext} from "../context/AuthContext";
import {ctfService} from "../services/Ctf/ctf.service";
import {SafeAgogeUser} from "../services/User/user.model";

// One lookup per signed-in user for the life of the page. Keyed by uid so a
// sign-out followed by a different sign-in never reuses the previous answer.
let cachedUid: string | null = null;
let cachedRequest: Promise<boolean> | null = null;

// GET /ctf/config/ is teacher_required, so anyone else would only collect a 403.
const configReaderUid = (user: SafeAgogeUser | null): string | null =>
    user?.uid && (user.permissions?.instructor === true || user.permissions?.admin === true) ? user.uid : null;

const fetchCtfEnabled = (uid: string): Promise<boolean> => {
    if (cachedUid !== uid || cachedRequest === null) {
        cachedUid = uid;
        // Concurrent callers share the in-flight request.
        cachedRequest = ctfService.getConfig()
            .then((config) => config.ctf_enabled)
            .catch(() => {
                // Fail closed, but forget the failure so a later mount can retry.
                if (cachedUid === uid) cachedRequest = null;
                return false;
            });
    }
    return cachedRequest;
};

/** Test-only: forget the cached answer. */
export const resetCtfEnabledCache = () => {
    cachedUid = null;
    cachedRequest = null;
};

export const useCtfEnabled = (): { ctfEnabled: boolean; loading: boolean } => {
    const {agogeUser: {user}} = useAuthContext();
    const uid = configReaderUid(user);
    const [state, setState] = useState<{ uid: string | null; enabled: boolean }>({uid: null, enabled: false});

    useEffect(() => {
        if (uid === null) return;
        let active = true;
        fetchCtfEnabled(uid).then((enabled) => {
            if (active) setState({uid, enabled});
        });
        return () => {
            active = false;
        };
    }, [uid]);

    // An answer for a previous user is never shown to the current one.
    const resolved = uid !== null && state.uid === uid;
    return {
        ctfEnabled: resolved && state.enabled,
        loading: uid !== null && !resolved,
    };
};
