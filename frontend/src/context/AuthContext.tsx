import {type User} from "firebase/auth";
import {createContext, useContext} from "react";
import {SafeAgogeUser} from "../services/User/user.model";

export interface AuthContextType {
    firebaseUser: {
        user: User | null;
        loading: boolean;
        getToken: () => Promise<string>;
    };
    agogeUser: {
        user: SafeAgogeUser | null;
        addUser: (value) => void;
        getUser: (idToken: string) => Promise<SafeAgogeUser | undefined>;
        sync: () => Promise<SafeAgogeUser | undefined>;
    };
    logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | null>(null);

export const useAuthContext = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an <AuthProvider>');
    }
    return context;
};
