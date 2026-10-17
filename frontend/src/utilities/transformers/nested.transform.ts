import {
    NestedBuildStatus,
    NestedGuest,
    NestedGuestNic,
    NestedHostSpec,
    NestedHostSpecInput,
    NestedIdResponse,
    NestedImageCreateRequest,
    NestedMedia,
    NestedMediaUploadResponse,
    NestedNetwork,
    NestedOsCatalogEntry,
} from "../../services/Server/nested.model";

// Each transformer copies only the modelled keys; nullable keys fall back to null and lists to []
// so the wizard and image details never guard against undefined from a sparse Firestore document.

const orNull = <T>(value: T | undefined | null): T | null => value ?? null;

export const transformToNestedOsCatalogEntry = (data: NestedOsCatalogEntry): NestedOsCatalogEntry => ({
    id: data.id,
    display_name: data.display_name,
    family: data.family,
    group: data.group,
    version: data.version,
    install_method: data.install_method,
    media_url: orNull(data.media_url),
    media_sha256: orNull(data.media_sha256),
    media_size_bytes: orNull(data.media_size_bytes),
    media_formats: data.media_formats ?? [],
    requires_upload: data.requires_upload === true,
    license_note: data.license_note ?? '',
    eval_days: orNull(data.eval_days),
    osinfo: data.osinfo,
    firmware: data.firmware ?? 'bios',
    disk_bus: data.disk_bus ?? 'virtio',
    nic_model: data.nic_model ?? 'virtio',
    video: data.video ?? 'vga',
    virtio_win_version: orNull(data.virtio_win_version),
    agent: data.agent === true,
    net_config: data.net_config,
    unattend_template: orNull(data.unattend_template),
    windows_image_index: orNull(data.windows_image_index),
    default_username: orNull(data.default_username),
    min_memory_mb: data.min_memory_mb,
    default_memory_mb: data.default_memory_mb,
    min_disk_gb: data.min_disk_gb,
    default_disk_gb: data.default_disk_gb,
    default_vcpus: data.default_vcpus ?? 1,
    // Anything but an explicit false stays selectable, matching the model's default.
    is_enabled: data.is_enabled !== false,
});

export const transformToNestedOsCatalog = (data: NestedOsCatalogEntry[]): NestedOsCatalogEntry[] =>
    (data ?? []).map(transformToNestedOsCatalogEntry);

export const transformToNestedMedia = (data: NestedMedia): NestedMedia => ({
    id: data.id,
    filename: data.filename,
    format: data.format,
    size_bytes: data.size_bytes,
    gcs_path: data.gcs_path,
    sha256: orNull(data.sha256),
    os_id: orNull(data.os_id),
    uploaded_by: data.uploaded_by,
    uploaded_at: data.uploaded_at,
    complete: data.complete === true,
});

export const transformToNestedMediaList = (data: NestedMedia[]): NestedMedia[] =>
    (data ?? []).map(transformToNestedMedia);

export const transformToNestedMediaUpload = (data: NestedMediaUploadResponse): NestedMediaUploadResponse => ({
    media_id: data.media_id,
    upload_url: data.upload_url,
    upload_headers: {...(data.upload_headers ?? {})},
    expires_in: data.expires_in,
});

// finalize_nonce is deliberately not copied: it is the handshake secret between the Cloud Function
// and the parent, and nothing in the UI needs it.
export const transformToNestedBuildStatus = (data: Partial<NestedBuildStatus> | null): NestedBuildStatus => ({
    phase: data?.phase ?? 'queued',
    guests: {...(data?.guests ?? {})},
    message: orNull(data?.message),
    heartbeat_at: orNull(data?.heartbeat_at),
    started_at: orNull(data?.started_at),
    updated_at: orNull(data?.updated_at),
});

export const transformToNestedIdResponse = (data: NestedIdResponse): NestedIdResponse => ({
    build_id: data.build_id,
});

const transformToNestedNetwork = (data: NestedNetwork): NestedNetwork => ({
    name: data.name,
    cidr: data.cidr,
    mode: data.mode,
    parent_address: orNull(data.parent_address),
    dhcp: data.dhcp !== false,
    dhcp_start: orNull(data.dhcp_start),
    dhcp_end: orNull(data.dhcp_end),
});

const transformToNestedGuestNic = (data: NestedGuestNic): NestedGuestNic => ({
    network: data.network,
    ip: orNull(data.ip),
    expose: data.expose === true,
});

const transformToNestedGuest = (data: NestedGuest): NestedGuest => ({
    name: data.name,
    os_id: data.os_id,
    media_id: orNull(data.media_id),
    vcpus: data.vcpus ?? 1,
    memory_mb: data.memory_mb ?? 2048,
    disk_gb: data.disk_gb ?? 20,
    nics: (data.nics ?? []).map(transformToNestedGuestNic),
    admin_username: data.admin_username,
    admin_password: data.admin_password ?? '',
    packages: [...(data.packages ?? [])],
    post_install_script: orNull(data.post_install_script),
    console: data.console !== false,
    autostart: data.autostart !== false,
    start_order: data.start_order ?? 0,
    start_delay_seconds: data.start_delay_seconds ?? 0,
});

const transformToNestedHostSpecInput = (data: NestedHostSpecInput): NestedHostSpecInput => ({
    parent_os: data.parent_os ?? 'debian-12',
    build_machine_type: data.build_machine_type ?? 'n2-standard-8',
    networks: (data.networks ?? []).map(transformToNestedNetwork),
    guests: (data.guests ?? []).map(transformToNestedGuest),
});

// Reads image.nested from a stored image record, including the fields the API derived.
export const transformToNestedHostSpec = (data: Partial<NestedHostSpec>): NestedHostSpec => ({
    ...transformToNestedHostSpecInput(data as NestedHostSpecInput),
    exposures: (data.exposures ?? []).map(([guest, nic]) => [guest, nic] as [string, number]),
    console_ports: {...(data.console_ports ?? {})},
    vnc_passwords: {...(data.vnc_passwords ?? {})},
});

// Builds the POST /compute/images/nested/ body. It rebuilds nested from the client-side fields only,
// so a spec loaded from an existing image (which carries exposures, console_ports and vnc_passwords)
// can be sent back without the API's "derived by the server" 400.
export const toNestedImageCreateRequest = (data: NestedImageCreateRequest): NestedImageCreateRequest => ({
    server_name: data.server_name.trim(),
    description: data.description,
    labels: [...(data.labels ?? [])],
    machine_type: data.machine_type,
    disk_size: orNull(data.disk_size),
    username: data.username.trim(),
    ssh_key: data.ssh_key.trim(),
    nested: transformToNestedHostSpecInput(data.nested),
    // A blank field means the guest has no key; drop it rather than hand the builder an empty one.
    product_keys: Object.fromEntries(
        Object.entries(data.product_keys ?? {})
            .map(([guest, key]) => [guest, key.trim()])
            .filter(([, key]) => key !== '')
    ),
});
