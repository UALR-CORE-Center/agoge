"""Constants for nested lab hosts and the nested image builder."""

# Images carrying this license boot with VMX exposed to the guest kernel, so a
# lab server built from a nested image gets nested virtualization without asking.
ENABLE_VMX_LICENSE = 'https://www.googleapis.com/compute/v1/projects/vm-options/global/licenses/enable-vmx'
NESTED_MACHINE_FAMILIES = ('n1', 'n2')
NESTED_MAX_MACHINE_MEMORY_MB = 65536
STANDARD_MAX_MACHINE_MEMORY_MB = 17000
