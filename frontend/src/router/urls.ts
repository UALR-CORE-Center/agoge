import {AppUiObjectNames, Users} from "../types/AppObjectNames";

export const
    // Main URLs
    URL_BASE: string = '/',
    URL_ERROR: string = '/error',
    URL_LOGIN: string = '/login',
    URL_LOGOUT: string = '/logout',
    URL_PRIVACY: string = '/privacy',
    URL_WHO_AM_I: string = 'whoami',

    // Teacher Routes
    URL_TEACHER_BASE: string = `/${Users.TEACHER.toLowerCase()}`,
    URL_TEACHER_MARKDOWN_EDITOR: string = `${URL_TEACHER_BASE}/editor`,
    URL_TEACHER_HOME: string = `${URL_TEACHER_BASE}/home`,
    URL_TEACHER_SETTINGS: string = `${URL_TEACHER_BASE}/settings`,
    URL_TEACHER_UNIT: string = `${URL_TEACHER_BASE}/${AppUiObjectNames.UNIT.toLowerCase()}`,
    URL_TEACHER_SPECIFICATIONS_BASE: string = `${URL_TEACHER_BASE}/specifications`,
    URL_TEACHER_SPECIFICATION_EDIT: string = `${URL_TEACHER_SPECIFICATIONS_BASE}/edit`,
    URL_TEACHER_SERVERS: string = `${URL_TEACHER_BASE}/servers/manage`,
    URL_TEACHER_SERVERS_CREATE: string = `${URL_TEACHER_BASE}/servers/create`,
    URL_TEACHER_SERVERS_EDITOR: string = `${URL_TEACHER_BASE}/servers/edit`,

    // Student Routes
    URL_STUDENT_BASE: string = `/${Users.STUDENT.toLowerCase()}`,
    URL_STUDENT_JOIN: string = `/join`,
    URL_STUDENT_WORKOUT: string = `${URL_STUDENT_BASE}/${AppUiObjectNames.WORKOUT.toLowerCase()}`,
    URL_STUDENT_WEBXR: string = `webxr`,

    // Admin Routes
    URL_ADMIN_BASE: string = `/${Users.ADMIN.toLowerCase()}`,
    URL_ADMIN_MANAGE_USERS: string = `${URL_ADMIN_BASE}/users`,
    URL_ADMIN_MANAGE_UNIT: string = `${URL_ADMIN_BASE}/manage/assignment`,
    URL_ADMIN_MANAGE_WORKOUT: string = `${URL_ADMIN_BASE}/manage/assignment/workout`,
    URL_ADMIN_MANAGE_IMAGES: string = `${URL_ADMIN_BASE}/manage/images`,
    URL_ADMIN_MANAGE_PROJECT: string = `${URL_ADMIN_BASE}/manage/project`,

    // Guacamole Routes
    URL_STUDENT_GUACAMOLE: string = `/${URL_STUDENT_WORKOUT}/:buildId/guacamole/:serverIdx`,
    URL_STUDENT_GUACAMOLE_TUNNEL: string = `${URL_STUDENT_WORKOUT}/{BUILD_ID}/guacamole/{SERVER_IDX}/session?token={TOKEN}`,

    // Docs Routes
    URL_DOCS_BASE: string = '/documents',
    URL_DOCS_EDITOR: string = `/${URL_DOCS_BASE}/edit/:file_uid`,
    URL_DOCS_VIEWER: string = `/${URL_DOCS_BASE}/:file_uid`,

    // Nerd Night Routes
    URL_PUZZLE_BASE: string = `/trivia`,
    URL_PUZZLE_ADMIN: string = `${URL_PUZZLE_BASE}/admin`,
    URL_PUZZLE_PLAYER: string = `${URL_PUZZLE_BASE}/play`,
    URL_PUZZLE_QUESTION_URL: string = `${URL_PUZZLE_PLAYER}/:question_id`,

    // API Routes
    URL_UNIT_API_BASE: string = "units/",
    URL_UNIT_API_ITEM: string = `${URL_UNIT_API_BASE}{ITEM_ID}/`,
    URL_UNIT_API_ITEM_STATE: string = `${URL_UNIT_API_ITEM}state/`,
    URL_UNIT_API_ITEM_ROSTER: string = `${URL_UNIT_API_ITEM}roster/`,
    URL_UNIT_API_ITEM_FULL: string = `${URL_UNIT_API_ITEM}full/`,
    URL_UNIT_API_ITEMS: string = `${URL_UNIT_API_BASE}{ITEM_ID}/workouts/`,
    URL_RUBRIC_API_BASE: string = "rubrics/",
    URL_RUBRIC_API_ITEM: string = `${URL_RUBRIC_API_BASE}{ITEM_ID}/`,
    URL_RUBRIC_API_GENERATE: string = `${URL_RUBRIC_API_BASE}generate/{BUILD_ID}/`,
    URL_WORKOUT_API_BASE: string = `workouts/`,
    URL_WORKOUT_API_ITEM: string = `${URL_WORKOUT_API_BASE}{ITEM_ID}/`,
    URL_WORKOUT_API_ITEM_STATE: string = `${URL_WORKOUT_API_ITEM}state/`,
    URL_WORKOUT_API_ITEM_FULL: string = `${URL_WORKOUT_API_BASE}{ITEM_ID}/full/`,
    URL_WORKOUT_QUESTION_API_ITEM: string = `${URL_WORKOUT_API_ITEM}question/{Q_KEY}/`,
    URL_WEBGL_API_BASE: string = `webxr/`,
    URL_ADMIN_API_PROJECT_BASE: string = `project/`,
    URL_USER_API_BASE: string = "users/",
    URL_USER_API_UID: string = `${URL_USER_API_BASE}{ITEM_ID}/`,
    URL_USER_API_SETTINGS: string = `${URL_USER_API_UID}settings/`,
    URL_USER_API_COURSES: string = `${URL_USER_API_UID}courses/`,
    URL_COMPUTE_IMAGE_API_BASE: string = "compute/images/",
    URL_COMPUTE_IMAGE_API_ITEM: string = `${URL_COMPUTE_IMAGE_API_BASE}{ITEM_ID}/`,
    URL_COMPUTE_IMAGE_API_CREATE: string = `${URL_COMPUTE_IMAGE_API_BASE}create/`,
    URL_COMPUTE_IMAGE_API_PROJECT: string = `${URL_COMPUTE_IMAGE_API_BASE}project/`,
    URL_COMPUTE_SNAPSHOT_API_BASE: string = "compute/snapshot/",
    URL_SPEC_API_BASE: string = "lab-specs/",
    URL_SPEC_STARTUP_SCRIPTS: string = `${URL_SPEC_API_BASE}startup-scripts/`,
    URL_SPEC_API_ITEM: string = `${URL_SPEC_API_BASE}{ITEM_ID}/`,
    URL_SPEC_API_UPLOAD: string = `${URL_SPEC_API_BASE}upload/`,
    URL_SPEC_API_EDIT: string = `${URL_SPEC_API_BASE}edit/`,
    URL_SPEC_API_EDIT_ITEM: string = `${URL_SPEC_API_EDIT}{ITEM_ID}/`,
    URL_DOCS_API_BASE: string = "docs/",
    URL_DOCS_API_ITEM: string = `${URL_DOCS_API_BASE}{ITEM_ID}/`,
    URL_DOCS_INSTRUCTIONS_API_BASE: string = `${URL_DOCS_API_BASE}instructions/`,
    URL_DOCS_INSTRUCTIONS_API_ITEM: string = `${URL_DOCS_API_BASE}instructions/{ITEM_ID}/`,
    URL_DOCS_INSTRUCTIONS_IMAGES: string = `${URL_DOCS_INSTRUCTIONS_API_BASE}images/`,
    URL_GUACAMOLE_API_BASE: string = "guacamole/",
    URL_GUACAMOLE_API_SESSION: string = `${URL_GUACAMOLE_API_BASE}{BUILD_ID}/servers/{SERVER_IDX}/`,

    //Lamp Control
    URL_PUZZLE_CONTROL_API_BASE: string = "puzzle-control/",
    URL_PUZZLE_CONTROL_QUESTION: string = `${URL_PUZZLE_CONTROL_API_BASE}question/{ITEM_ID}/`,
    URL_PUZZLE_CONTROL_COMMAND: string = `${URL_PUZZLE_CONTROL_API_BASE}{DEVICE_ID}/{SKU}/command/`
;