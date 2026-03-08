import {onIdTokenChanged, signOut, type User} from "firebase/auth";
import React, {useEffect, useState} from "react";
import {auth} from "../components/AgogeAuth/Firebase/firebaseConfig";
import {SpinnerOverlay} from "../components/Common/SpinnerOverlay";
import {AuthContext} from "../context/AuthContext";
import {useLocalStorage} from "../hooks/useLocalStorage";
import {SafeAgogeUser} from "../services/User/user.model";
import {apiUrl} from "../utilities/apiClient";

export const AuthProvider: React.FC<{children: React.ReactNode }> = ({children}) => {
    const authUrl = apiUrl("auth/");
    const localStorageKey = 'agogeUser';
    const { setItem, getItem } = useLocalStorage();
    const [appUser, setAppUser] = useState<SafeAgogeUser | null>(() => {
        const raw = getItem(localStorageKey);
        return raw ? JSON.parse(raw) : null;
    });
    const [firebaseUser, setFirebaseUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);

    /* LocalStorage user functions */
    const getUser = async (idToken: string): Promise<SafeAgogeUser | undefined> => {
        try {
            const response = await fetch(authUrl, {
                method: 'POST',
                headers: {"Authorization": `Bearer ${idToken}`}
            });

            const result = await response.json();
            const newAppUser = result.data ?? null;
            if (newAppUser !== null) {
                addUser(newAppUser);
                return newAppUser;
            }
        } catch (error) {
            console.error(error.message || 'Unknown error', error);
        }
        return undefined;
    };

    // Save SafeAgogeUser to localStorage
    const addUser = (newAppUser: SafeAgogeUser) => {
        setAppUser(newAppUser);
        setItem(localStorageKey, JSON.stringify(newAppUser));
    };

    // Remove SafeAgogeUser from localStorage
    const removeUser = () => {
        setAppUser(null);
        setItem(localStorageKey, "");
    };

    const logout = async () => {
        await signOut(auth).then(() => {
            removeUser();
        }).catch((error) => {
            console.log(error);
        });
    };

    const sync = async () => {
        const idToken = await getFirebaseToken();
        const updatedUser = await getUser(idToken);
        if (updatedUser) {
            setAppUser(updatedUser);
        }

        return updatedUser;
    };

    const getFirebaseToken = async (): Promise<string> => {
        if (!auth.currentUser && loading) {
            return
        } else if (!auth.currentUser && !loading && !firebaseUser) {
            throw new Error("Not signed in");
        }
        return auth.currentUser.getIdToken();
    };

    useEffect(() => {
        let isFirstCall = true;
        return onIdTokenChanged(auth, async (user) => {
            if (isFirstCall) {
                isFirstCall = false;
                setFirebaseUser(user);
                setLoading(false);

                // if there's already a user, fetch them once
                if (user) {
                    try {
                        const token = await user.getIdToken();
                        const json = await fetch(authUrl, {
                            method: "POST",
                            headers: {Authorization: `Bearer ${token}`},
                        }).then(r => r.json());
                        addUser(json.data);
                    } catch {
                        // swallow
                    }
                }
                return;
            }
            setFirebaseUser(user);
            setLoading(false);

            if (!user) {
                removeUser();
            } else {
                // re-fetch your app user, or sync()
                const token = await user.getIdToken();
                await getUser(token);
            }
        });
    }, [authUrl]);

    const ctxValue = {
        firebaseUser: {
            user: firebaseUser,
            loading: loading,
            getToken: getFirebaseToken,
        },
        agogeUser: {
            getUser,
            addUser: addUser,
            sync: sync,
            user: appUser,
        },
        logout,
    };

    if (loading) return <SpinnerOverlay />

    return (
        <AuthContext.Provider value={ctxValue}>
            {children}
        </AuthContext.Provider>
    );
};
