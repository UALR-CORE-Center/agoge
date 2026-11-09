import React from "react";
import {Navigate} from "react-router-dom";
import {SpinnerOverlay} from "../components/Common/SpinnerOverlay";
import {useAuthContext} from "../context/AuthContext";
import {URL_LOGOUT} from "./urls";

export type Permission = "admin" | "instructor" | "student" | "staff";

interface ProtectedRouteProps {
    element: React.ReactElement;
    level?: Permission;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
    element,
    level
}) => {
    const {
        firebaseUser: {user, loading},
        agogeUser,
    } = useAuthContext();

    if (loading) return <SpinnerOverlay />

    // no Firebase user is logged out
    if (!user) return <Navigate to={URL_LOGOUT} replace />;

    // no app-user yet? wait for sync
    if (!agogeUser?.user) {
        agogeUser.sync();
        return <SpinnerOverlay />;
    }

    const permissions = agogeUser.user.permissions;
    if (level && !(level === "staff" ? permissions?.admin || permissions?.instructor : permissions?.[level])) {
        return <Navigate to={URL_LOGOUT} replace />;
    }

    return element;
};
