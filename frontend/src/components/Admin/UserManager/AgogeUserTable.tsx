import {
    Edit as EditIcon,
    Delete as DeleteIcon,
    Done, Clear
} from '@mui/icons-material';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import SaveIcon from '@mui/icons-material/Save';
import {LoadingButton} from "@mui/lab";
import {
    Box,
    Checkbox,
    Chip,
    IconButton,
    Tooltip,
    useTheme
} from '@mui/material';
import {GridColDef} from "@mui/x-data-grid";
import {useModal} from "mui-modal-provider";
import React, { useState, useEffect } from 'react';
import { AgogeUser } from '../../../services/User/user.model';
import { userService } from '../../../services/User/user.service';
import {ExpandableCell} from "../../Common/DataGrid/ExpandableCell";
import StyledDataGrid, {ButtonConfig} from "../../Common/DataGrid/StyledDataGrid";
import SimpleSnackbar from "../../Common/SnackBar/SnackBar";
import {CreateUserDialog} from "./CreateUserDialog";
import {DeleteUserDialog} from "./DeleteUserDialog";

const AgogeUserTable: React.FC = () => {
    const theme = useTheme();
    const {showModal} = useModal();

    const [userList, setUserList] = useState<AgogeUser[]>([]);
    const [filteredUsers, setFilteredUsers] = useState<AgogeUser[]>([]);
    const [isLoading, setLoading] = useState<boolean>(true);

    // Separate loading check for save and create user buttons
    const [activeAction, setActiveAction] = useState<string | null>(null);
    const [editRowId, setEditRowId] = useState<string | null>(null);
    const [openModal, setOpenModal] = useState<boolean>(false);
    const [selectedUser, setSelectedUser] = useState<AgogeUser | null>(null);
    const [editedPermissions, setEditedPermissions] = useState<{ [key: string]: boolean }>({});

    const [createUserModalOpen, setCreateUserModalOpen] = useState<boolean>(false);

    useEffect(() => {
        const fetchUsers = async () => {
            try {
                const fetchedUsers = await userService.list();
                const usersWithId = fetchedUsers.map(user => ({
                    ...user,
                    id: user.uid,
                }));
                setUserList(usersWithId);
                setLoading(false);
            } catch (error) {
                setLoading(false);
            }
        };
        fetchUsers();
    }, []);

    useEffect(() => {
        const flattenData = () => {
            const flattened = userList.map(item => ({
                id: item.uid,
                uid: item.uid,
                name: item.name || 'N/A',
                email: item.email,
                permissions: item?.permissions || {admin: false, instructor: false, student: false},
                settings: item.settings,
                timezone: item.timezone
            }));

            setFilteredUsers(flattened);
        };

        flattenData();
    }, [userList]);

    const handleEditClick = (rowId: string) => {
        setEditRowId(editRowId === rowId ? null : rowId);
        const user = userList.find(user => user.email === rowId);
        setEditedPermissions(user?.permissions || {});
        setSelectedUser(user || null);
    };

    const handleCheckboxChange = (role: string) => {
        setEditedPermissions(prevPermissions => ({
            ...prevPermissions,
            [role]: !prevPermissions[role]
        }));
    };

    const handleSaveClick = async () => {
        let hasError = false;
        if (selectedUser) {
            setActiveAction('saveUser');
            selectedUser.permissions = editedPermissions;
            try {
                await userService.update_permissions(selectedUser.uid, selectedUser);
                showModal(SimpleSnackbar, {
                    message: "Successfully updated settings!",
                    severity: "success"
                });
            } catch (error) {
                showModal(SimpleSnackbar, {
                    message: "Failed to update user settings.",
                    severity: "error"
                });
                hasError = true;
            } finally {
                setActiveAction(null);
                setSelectedUser(null);
            }
        }
        if (editRowId && !hasError) {
            const updatedUserList = userList.map(user => {
                if (user.email === editRowId) {
                    return { ...user, permissions: editedPermissions, id: user.uid };
                }
                return user;
            });
            setUserList(updatedUserList);
            setFilteredUsers(updatedUserList);
        }
        setEditRowId(null);
    };

    const handleDeleteClick = (user: AgogeUser) => {
        setSelectedUser(user);
        setOpenModal(true);
    };

    const handleModalClose = () => {
        setOpenModal(false);
        setSelectedUser(null);
    };

    const handleCreateUserClick = () => {
        setCreateUserModalOpen(true);
    };

    const handleCreateUserModalClose = () => {
        setCreateUserModalOpen(false);
    };

    const handleUpdateUserList = (new_user: AgogeUser, filter: boolean = false) => {
        if (!filter) {
            setUserList([...userList, new_user]);
        } else if (selectedUser && filter) {
            setUserList(
                prevUserList =>
                    prevUserList.filter(user => user.uid !== new_user.uid)
            );
        }
    }

    const getButtonConfig = () => {
        const buttonConfig: ButtonConfig[] = [
            {
                label: "Create User",
                variant: 'contained',
                color: 'primary',
                icon: <PersonAddIcon />,
                requiresSelection: false,
                addTooltip: true,
                tooltip: "Create new user",
                onClick: handleCreateUserClick
            }
        ];

        return buttonConfig;
    }

    const isUserPending = (user: AgogeUser) => {
        return !user.permissions?.admin && !user.permissions?.instructor && !user.permissions?.student;
    };

    const renderPermissionsCell = (params: any, role: string) => {
        const isEditing = editRowId === params.row.email;
        if (isEditing) {
            return (
                <Checkbox
                    checked={editedPermissions[role] || false}
                    onChange={() => handleCheckboxChange(role)}
                />
            );
        } else if (params.row.permissions[role]) {
            return (<Done color={"success"} aria-hidden={false} aria-label={`${role} permission granted`}/>);
        } else {
            return (<Clear color={"error"} aria-hidden={false} aria-label={`${role} permission denied`}/>);
        }
    };

    const columns: GridColDef[]  = [
        {
            field: 'email',
            headerName: 'User',
            width: 300,
            sortable: true,
            filterable: true,
            flex: 1,
            renderCell: (params: any) => (
                <ExpandableCell
                    {...params}
                    value={params.row.email}
                    variant={"body1"}
                />
            )
        },
        {
            field: 'pending',
            headerName: 'Status',
            width: 100,
            sortable: false,
            renderCell: (params: any) => {
                if (isUserPending(params.row)) {
                    return (
                        <Chip
                            variant={"outlined"}
                            color={"warning"}
                            label="Pending"
                            style={{ borderRadius: '3px'}}
                        />
                    );
                } else {
                    return (
                        <Chip
                            variant={"outlined"}
                            color={theme.palette.mode === 'dark' ? "info" : "default"}
                            label="Active"
                            style={{ borderRadius: '3px' }}
                        />
                    );
                }
            }
        },
        {
            field: 'admin',
            headerName: 'Admin',
            width: 100,
            sortable: false,
            renderCell: (params: any) => renderPermissionsCell(params, 'admin')
        },
        {
            field: 'instructor',
            headerName: 'Instructor',
            width: 105,
            sortable: false,
            renderCell: (params: any) => renderPermissionsCell(params, 'instructor')
        },
        {
            field: 'student',
            headerName: 'Student',
            width: 100,
            sortable: false,
            renderCell: (params: any) => renderPermissionsCell(params, 'student')
        },
        {
            field: 'actions',
            headerName: 'Actions',
            flex: 1,
            sortable: false,
            filterable: false,
            renderCell: (params: any) => (
                <Box>
                    <Tooltip title="Edit">
                        <IconButton onClick={() => handleEditClick(params.row.email)} aria-label={`Edit ${params.row.email}`}>
                            <EditIcon />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                        <IconButton onClick={() => handleDeleteClick(params.row)} aria-label={`Delete ${params.row.email}`}>
                            <DeleteIcon />
                        </IconButton>
                    </Tooltip>
                    {editRowId === params.row.email && (
                        <LoadingButton
                            onClick={handleSaveClick}
                            variant="contained"
                            color="primary"
                            startIcon={<SaveIcon />}
                            loading={activeAction === 'saveUser'}
                            loadingPosition="start"
                        >
                            Save
                        </LoadingButton>
                    )}
                </Box>
            )
        }
    ];

    return (
        <Box sx={{ height: "auto", width: "100%" }}>
            <Box sx={{ width: 'auto', m: 5 }}>
                <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                    <StyledDataGrid
                        data={filteredUsers}
                        columns={columns}
                        disableCheckBoxes={true}
                        density={"standard"}
                        loading={isLoading}
                        labelProps={{
                            disable: true
                        }}
                        buttonsConfig={getButtonConfig()}
                        initialState={{
                            sorting: {
                                sortModel: [{field: 'email', sort: 'asc'}]
                            },
                        }}
                        getRowId={(row) => row.uid}
                    />
                </Box>

                <DeleteUserDialog
                    open={openModal}
                    selectedUser={selectedUser}
                    handleClose={handleModalClose}
                    updateUserList={handleUpdateUserList}
                />

                <CreateUserDialog
                    open={createUserModalOpen}
                    handleClose={handleCreateUserModalClose}
                    updateUserList={handleUpdateUserList}
                />
            </Box>
        </Box>
    );
};

export default AgogeUserTable;