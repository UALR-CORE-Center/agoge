import {AgogeUser, UserCourses, LMSCourse} from "../../services/User/user.model";


export const transformToAgogeUser = (data: any): AgogeUser => {
    return {
        uid: data.uid?? '',
        email: data.email?? '',
        name: data.name?? '',
        permissions: data.permissions,
        settings: data.settings,
        timezone: data.timezone,
    };
};

export const transformToCourse = (course: any): LMSCourse => {
    return {
        id: course.id,
        name: course.name,
    };
};

export const transformToCoursesList = (data: any): UserCourses => {
    const transformedCourses: UserCourses = {};
    if (data.canvas) {
        transformedCourses.canvas = data.canvas.map((course: any) => transformToCourse(course));
    }
    if (data.blackboard) {
        transformedCourses.blackboard = data.blackboard.map((course: any) => transformToCourse(course));
    }
    if (data.classroom) {
        transformedCourses.classroom = data.classroom.map((course: any) => transformToCourse(course));
    }
    return transformedCourses;
};

export const transformToUserList = (data: any[]): AgogeUser[] => {
    return data.map(transformToAgogeUser);
};
