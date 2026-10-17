// Wire shapes for the nested lab host routes; they mirror the Nested* models in common/models/agoge.py.

export type NestedOsFamily = 'linux' | 'windows' | 'appliance';
export type NestedOsGroup = 'kali' | 'linux' | 'windows_client' | 'windows_server' | 'appliance';
export type NestedInstallMethod = 'cloud_image' | 'unattended_iso' | 'disk_image' | 'manual_iso';
export type NestedMediaFormat =
    'qcow2' | 'raw' | 'img.xz' | 'img.bz2' | 'tar.xz' | 'iso' | 'iso.gz' | 'vmdk' | 'vhd' | 'vhdx' | 'ova' | 'zip' | '7z';
export type NestedNetConfig = 'networkd' | 'netplan' | 'nm-keyfile' | 'ifupdown' | 'windows' | 'none';
export type NestedGuestStatus =
    'pending' | 'downloading' | 'installing' | 'post_install' | 'manual' | 'ready' | 'failed';
export type NestedBuildPhase =
    'queued' | 'provisioning' | 'building' | 'ready' | 'finalizing' | 'finalized' | 'failed';
export type NestedParentOs = 'debian-12' | 'debian-13';
export type NestedNetworkMode = 'nat' | 'isolated';

export interface NestedOsCatalogEntry {
    id: string;
    display_name: string;
    family: NestedOsFamily;
    group: NestedOsGroup;
    version: string;
    install_method: NestedInstallMethod;
    media_url: string | null;
    media_sha256: string | null;
    // Content-Length of media_url; null for upload-only entries and entries synced before it existed.
    media_size_bytes: number | null;
    media_formats: NestedMediaFormat[];
    requires_upload: boolean;
    license_note: string;
    eval_days: number | null;
    osinfo: string;
    firmware: 'bios' | 'uefi';
    disk_bus: 'virtio' | 'sata' | 'ide';
    nic_model: 'virtio' | 'e1000e' | 'e1000' | 'rtl8139';
    video: 'virtio' | 'qxl' | 'vga' | 'cirrus';
    virtio_win_version: string | null;
    agent: boolean;
    net_config: NestedNetConfig;
    unattend_template: 'autounattend' | null;
    windows_image_index: number | null;
    default_username: string | null;
    min_memory_mb: number;
    default_memory_mb: number;
    min_disk_gb: number;
    default_disk_gb: number;
    default_vcpus: number;
    is_enabled: boolean;
}

export interface NestedMedia {
    id: string;
    filename: string;
    format: NestedMediaFormat;
    size_bytes: number;
    gcs_path: string;
    sha256: string | null;
    os_id: string | null;
    uploaded_by: string;
    uploaded_at: string;
    complete: boolean;
}

export interface NestedMediaCreateRequest {
    filename: string;
    size_bytes: number;
    os_id?: string | null;
}

export interface NestedMediaUploadResponse {
    media_id: string;
    // A V4 signed URL: POST it with exactly upload_headers to open a resumable session.
    upload_url: string;
    upload_headers: Record<string, string>;
    expires_in: number;
}

export interface NestedNetwork {
    name: string;
    cidr: string;
    mode: NestedNetworkMode;
    parent_address: string | null;
    dhcp: boolean;
    dhcp_start: string | null;
    dhcp_end: string | null;
}

export interface NestedGuestNic {
    network: string;
    ip: string | null;
    expose: boolean;
}

export interface NestedGuest {
    name: string;
    os_id: string;
    media_id: string | null;
    vcpus: number;
    memory_mb: number;
    disk_gb: number;
    nics: NestedGuestNic[];
    admin_username: string;
    admin_password: string;
    packages: string[];
    post_install_script: string | null;
    console: boolean;
    autostart: boolean;
    start_order: number;
    start_delay_seconds: number;
}

// The fields a client may send. The API derives exposures, console ports and VNC passwords and
// rejects a create request that carries any of them.
export interface NestedHostSpecInput {
    parent_os: NestedParentOs;
    build_machine_type: string;
    networks: NestedNetwork[];
    guests: NestedGuest[];
}

export interface NestedHostSpec extends NestedHostSpecInput {
    // (guest, nic index); the list index is the alias slot on the lab server.
    exposures: [string, number][];
    console_ports: Record<string, number>;
    vnc_passwords: Record<string, string>;
}

export interface NestedBuildStatus {
    phase: NestedBuildPhase;
    guests: Record<string, NestedGuestStatus>;
    message: string | null;
    heartbeat_at: string | null;
    started_at: string | null;
    updated_at: string | null;
}

export interface NestedImageCreateRequest {
    server_name: string;
    description: string;
    labels: string[];
    machine_type: string;
    // null = the API computes the minimum.
    disk_size: number | null;
    username: string;
    ssh_key: string;
    nested: NestedHostSpecInput;
    // guest -> product key; sent once and never persisted.
    product_keys: Record<string, string>;
}

export interface NestedIdResponse {
    build_id: string;
}
