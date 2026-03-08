import React, {useState} from 'react';
import {
    createBrowserRouter,
    RouterProvider,
    Navigate,
} from 'react-router-dom';

import {GlobalImageManager} from "../components/Admin/GlobalImageManager/GlobalImageManager";
import ProjectOverviewTabs from "../components/Admin/ProjectOverviewTabs";
import {ProjectSettings} from "../components/Admin/ProjectSettings/ProjectSettings";
import UserManager from "../components/Admin/UserManager/UserManager"
import Login from '../components/AgogeAuth/Login';
import Logout from "../components/AgogeAuth/Logout";
import AppError from "../components/Common/Errors/AppError";
import {InfoDrawer} from "../components/Common/InfoDrawer/InfoDrawer";
import {DrawerProvider} from "../components/Common/InfoDrawer/InfoDrawerContext";
import Layout from "../components/Common/Layout";
import SessionWaitDialog from "../components/Guacamole/SessionWaitDialog";
import MarkdownEditor from "../components/Markdown/MarkdownEditor";
import MarkdownViewer from "../components/Markdown/MarkdownViewer";
import PuzzleAdminPanel from "../components/PuzzleControl/PuzzleAdminPanel";
import PlayerHomePage from "../components/PuzzleControl/PuzzlePlayerHome";
import PuzzleQuestionPage from "../components/PuzzleControl/PuzzleQuestionPage";
import JoinWorkout from "../components/Student/JoinWorkout";
import StudentWorkout from "../components/Student/Workout";
import TeacherHome from '../components/Teacher/Home/Home';
import ServerCreatorForm from "../components/Teacher/ServerManagement/Forms/ServerCreator/ServerCreatorForm";
import { ServerEditorForm } from "../components/Teacher/ServerManagement/Forms/ServerEditor/ServerEditorForm";
import ServerManager from "../components/Teacher/ServerManagement/ServerManager";
import TeacherSettings from "../components/Teacher/Settings/Settings";
import Editor from "../components/Teacher/Specifications/NewEditor/Editor";
import CatalogEditTable from "../components/Teacher/Specifications/SpecificationTables/CatalogEditTable";
import CatalogTable from "../components/Teacher/Specifications/SpecificationTables/CatalogTable";
import TeacherUnit from "../components/Teacher/Unit/TeacherUnit";
import {useAuthContext} from "../context/AuthContext";
import {BASENAME} from "../utilities/appContext";
import {ProtectedRoute} from "./ProtectedRoute";
import {
    URL_LOGIN,
    URL_LOGOUT,
    URL_TEACHER_HOME,
    URL_TEACHER_SETTINGS,
    URL_TEACHER_UNIT,
    URL_TEACHER_SPECIFICATION_EDIT,
    URL_TEACHER_SERVERS,
    URL_TEACHER_SERVERS_CREATE,
    URL_TEACHER_SERVERS_EDITOR,
    URL_STUDENT_JOIN,
    URL_STUDENT_WORKOUT,
    URL_ADMIN_MANAGE_USERS,
    URL_STUDENT_GUACAMOLE,
    URL_TEACHER_SPECIFICATIONS_BASE,
    URL_ADMIN_BASE,
    URL_ADMIN_MANAGE_PROJECT,
    URL_ADMIN_MANAGE_IMAGES,
    URL_DOCS_EDITOR,
    URL_DOCS_VIEWER,
    URL_PUZZLE_ADMIN,
    URL_PUZZLE_PLAYER
} from './urls';


const DefaultHome: React.FC = () => {
    const { firebaseUser, agogeUser } = useAuthContext();
    return (
            firebaseUser?.user && agogeUser?.user
            ? <Navigate to={URL_TEACHER_HOME} replace={true}/>
            : <Navigate to={URL_LOGIN} replace={true}/>
        );
};


interface AppRouterProps {toggleTheme: (event: React.ChangeEvent<HTMLInputElement>, checked: boolean) => void;
    isDarkMode: boolean;
}

const AppRouter: React.FC<AppRouterProps> = ({ toggleTheme, isDarkMode }) => {
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const toggleSidebar = () => setSidebarOpen(!sidebarOpen);

    const router = createBrowserRouter([
            {
                path: "/",
                element: <Layout toggleTheme={toggleTheme} isDarkMode={isDarkMode} onSidebarToggle={toggleSidebar} />,
                errorElement: <AppError />,
                children: [
                    { index: true, element: <DefaultHome /> },
                    { path: URL_TEACHER_HOME, element: <ProtectedRoute element={<TeacherHome />} level={"instructor"} /> },
                    { path: URL_TEACHER_SETTINGS, element: <ProtectedRoute element={<TeacherSettings />} level={"instructor"} /> },
                    { path: URL_TEACHER_SERVERS, element: <ProtectedRoute element={<ServerManager />} level={"instructor"} /> },
                    { path: URL_TEACHER_SERVERS_CREATE, element: <ProtectedRoute element={<ServerCreatorForm />} level={"instructor"} /> },
                    { path: `${URL_TEACHER_SERVERS_EDITOR}/:image_id`, element: <ProtectedRoute element={<ServerEditorForm />} minPermission={"instructor"} /> },
                    { path: URL_TEACHER_SPECIFICATIONS_BASE, element: <ProtectedRoute element={<CatalogTable />} level={"instructor"} /> },
                    { path: URL_TEACHER_SPECIFICATION_EDIT, element: <ProtectedRoute element={<CatalogEditTable />} level={"instructor"} /> },
                    { path: `${URL_TEACHER_SPECIFICATION_EDIT}/:edit_id`, element: <ProtectedRoute element={<Editor />} level={"instructor"} /> },
                    { path: `${URL_TEACHER_UNIT}/:build_id`, element: <ProtectedRoute element={<TeacherUnit />} level={"instructor"} /> },
                    { path: URL_ADMIN_BASE, element: <ProtectedRoute element={<ProjectOverviewTabs />} level={"admin"} />},
                    { path: URL_ADMIN_MANAGE_USERS, element: <ProtectedRoute element={<UserManager />} level={"admin"} />},
                    { path: URL_ADMIN_MANAGE_IMAGES, element: <ProtectedRoute element={<GlobalImageManager />} level={"admin"} />},
                    { path: URL_ADMIN_MANAGE_PROJECT, element: <ProtectedRoute element={<ProjectSettings />} level={"admin"} />},

                    // Public Endpoints
                    { path: `${URL_STUDENT_WORKOUT}/:build_id`, element: <StudentWorkout /> },
                    { path: URL_DOCS_EDITOR, element: <ProtectedRoute element={<MarkdownEditor/>} />},
                    { path: URL_DOCS_VIEWER, element: <MarkdownViewer /> },
                ],
            },
            { path: "error", element: <AppError /> },
            { path: URL_LOGIN, element: <Login /> },
            { path: URL_LOGOUT, element: <Logout /> },
            { path: URL_STUDENT_GUACAMOLE, element: <SessionWaitDialog /> },
            { path: URL_STUDENT_JOIN, element: <JoinWorkout /> },
            {
                path: URL_PUZZLE_ADMIN,
                element: <PuzzleAdminPanel />,
                errorElement: <AppError />,
            },
            {
                path: URL_PUZZLE_PLAYER,
                element: <PlayerHomePage />,
            },
            {
                path: `${URL_PUZZLE_PLAYER}/:join_code`,
                element: <PuzzleQuestionPage/>
            },
        ],
        {basename: BASENAME}
    );

    return (
        <DrawerProvider>
            <RouterProvider router={router} />
            <InfoDrawer />
        </DrawerProvider>
    );
};

export default AppRouter;