"""Constants for nested lab hosts and the nested image builder."""

# Images carrying this license boot with VMX exposed to the guest kernel, so a
# lab server built from a nested image gets nested virtualization without asking.
ENABLE_VMX_LICENSE = 'https://www.googleapis.com/compute/v1/projects/vm-options/global/licenses/enable-vmx'
NESTED_MACHINE_FAMILIES = ('n1', 'n2')
NESTED_MAX_MACHINE_MEMORY_MB = 65536
STANDARD_MAX_MACHINE_MEMORY_MB = 17000

NESTED_PARENT_OVERHEAD_MB = 2048
NESTED_PARENT_BASE_DISK_GB = 20
NESTED_BUILD_SCRATCH_GB = 12
NESTED_MAX_DISK_GB = 1000
NESTED_MAX_EXPOSURES = 8
NESTED_CONSOLE_BASE_PORT = 5901
# Must stay below the 540 s Cloud Function timeout, leaving room for the CHECK_IN publish.
NESTED_FINALIZE_TIMEOUT_SECONDS = 360
NESTED_BUILD_STALL_MINUTES = 45
NESTED_BUILD_MAX_MINUTES = 240
NESTED_MEDIA_MAX_BYTES = 21474836480  # 20 GiB
NESTED_UPLOAD_URL_TTL_SECONDS = 3600
# The media bucket is <project>_nested-media.
NESTED_MEDIA_BUCKET_SUFFIX = 'nested-media'
