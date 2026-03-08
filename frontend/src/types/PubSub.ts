export class PubSub {
    static Actions = {
        BUILD: 1,
        START: 2,
        DELETE: 3,
        STOP: 4,
        REBUILD: 5,
        SNAPSHOT: 6,
        RESTORE: 7,
        NUKE: 8,
        SYNC: 9,
        CANCEL: 10,
        UPDATE: 11,
        RESET_EXPIRATION: 12,
        EXTEND_RUNTIME: 13,
        CHECK_IN: 16,
        CHECK_OUT: 17,
    };

    static CourseObjects = {
        DISK: 1,
        DISPLAY_PROXY: 2,
        FIREWALL_SERVER: 3,
        IMAGE: 4,
        INSTANCE: 5,
        LAB_SERVER: 6,
        PUBLIC_IMAGE: 7,
        SNAPSHOT: 8,
        TEMPLATE_SERVER: 9,
        UNIT: 10,
        WORKOUT: 11,
    }
}
