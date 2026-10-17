import {describe, expect, it} from "vitest";
import {NestedGuest} from "../../../../../services/Server/nested.model";
import {ServerMachineTypes} from "../../../../../services/Specification/specificationEdit.model";
import {
    effectiveDiskSize,
    initialNestedWizardState,
    NestedWizardState,
    NestedWizardSteps,
    nestedMinDiskSize,
    resolveNavigation,
    validateHostStep,
    validateNestedServerName,
    validateStep,
} from "./nestedWizardState";

const machineTypes: ServerMachineTypes[] = [
    {id: "1", name: "n2-standard-8", description: "", is_shared_core: false, memory_mb: 32768, guest_cpus: 8},
    {id: "2", name: "n1-standard-4", description: "", is_shared_core: false, memory_mb: 15360, guest_cpus: 4},
];

const guest = (name: string, disk_gb: number): NestedGuest => ({
    name,
    os_id: "debian-12",
    media_id: null,
    vcpus: 1,
    memory_mb: 2048,
    disk_gb,
    nics: [{network: "lab", ip: null, expose: false}],
    admin_username: "student",
    admin_password: "Passw0rd!",
    packages: [],
    post_install_script: null,
    console: true,
    autostart: true,
    start_order: 0,
    start_delay_seconds: 0,
});

const validHost = (overrides: Partial<NestedWizardState> = {}): NestedWizardState => ({
    ...initialNestedWizardState(),
    server_name: "ad-lab-host",
    description: "Domain controller and two clients",
    machine_type: "n1-standard-4",
    username: "gm",
    ssh_key: "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl gm@laptop",
    ...overrides,
});

describe("nestedWizardState", () => {
    it("starts with the lab NAT network, no guests, and the default build machine type", () => {
        const state = initialNestedWizardState();
        expect(state.networks).toEqual([{
            name: "lab", cidr: "192.168.100.0/24", mode: "nat", parent_address: "192.168.100.1",
            dhcp: true, dhcp_start: "192.168.100.100", dhcp_end: "192.168.100.199",
        }]);
        expect(state.guests).toEqual([]);
        expect(state.build_machine_type).toBe("n2-standard-8");
        expect(state.disk_size).toBeNull();
    });

    it("computes the minimum disk as parent base + guest disks + build scratch", () => {
        expect(nestedMinDiskSize([])).toBe(32);
        expect(nestedMinDiskSize([guest("kali", 40), guest("dc", 60)])).toBe(132);
        // An unset size shows the minimum; a chosen size wins.
        expect(effectiveDiskSize(validHost({guests: [guest("kali", 40)]}))).toBe(72);
        expect(effectiveDiskSize(validHost({disk_size: 200}))).toBe(200);
    });

    it("accepts a complete Host step", () => {
        expect(validateHostStep(validHost(), machineTypes)).toEqual({});
    });

    it("flags every empty required Host field", () => {
        const errors = validateHostStep({...initialNestedWizardState(), build_machine_type: ""}, machineTypes);
        expect(Object.keys(errors).sort()).toEqual(
            ["build_machine_type", "description", "machine_type", "server_name", "ssh_key", "username"]
        );
    });

    it.each([
        ["Upper", true],
        ["ends-with-", true],
        ["1starts-with-digit", true],
        ["a".repeat(55), true],
        ["image-foo", true],
        ["nested", true],
        ["agoge", true],
        ["google", true],
        ["a".repeat(54), false],
        ["x", false],
        ["lab-host-2", false],
    ])("server name %s is rejected: %s", (name, rejected) => {
        expect(!!validateNestedServerName(name)).toBe(rejected);
    });

    it("rejects a description over 200 characters", () => {
        expect(validateHostStep(validHost({description: "d".repeat(201)}), machineTypes).description)
            .toMatch(/200/);
    });

    it("rejects a machine type outside the nested-capable list", () => {
        const errors = validateHostStep(validHost({machine_type: "e2-standard-8"}), machineTypes);
        expect(errors.machine_type).toMatch(/N1 or N2/);
        // While the list has not loaded, a chosen value is not second-guessed.
        expect(validateHostStep(validHost({machine_type: "e2-standard-8"}), []).machine_type).toBeUndefined();
    });

    it("lets the disk size go up from the computed minimum but not below it or above 1000 GB", () => {
        const guests = [guest("kali", 40)];
        expect(validateHostStep(validHost({guests, disk_size: 72}), machineTypes).disk_size).toBeUndefined();
        expect(validateHostStep(validHost({guests, disk_size: 500}), machineTypes).disk_size).toBeUndefined();
        expect(validateHostStep(validHost({guests, disk_size: 71}), machineTypes).disk_size).toMatch(/72 to 1000/);
        expect(validateHostStep(validHost({guests, disk_size: 1001}), machineTypes).disk_size).toBeDefined();
        expect(validateHostStep(validHost({guests, disk_size: 80.5}), machineTypes).disk_size).toBeDefined();
    });

    it("applies the API's username rule and requires an OpenSSH public key", () => {
        expect(validateHostStep(validHost({username: "bad user"}), machineTypes).username).toBeDefined();
        expect(validateHostStep(validHost({username: "u".repeat(21)}), machineTypes).username).toBeDefined();
        expect(validateHostStep(validHost({ssh_key: "not a key"}), machineTypes).ssh_key).toBeDefined();
        expect(validateHostStep(validHost({ssh_key: "ssh-rsa AAAAB3NzaC1yc2E="}), machineTypes).ssh_key)
            .toBeUndefined();
    });

    it("requires a network and a guest, and Review names the first broken step", () => {
        expect(validateStep(NestedWizardSteps.Networks, validHost({networks: []}), machineTypes)).toEqual(
            {networks: "Add at least one network."}
        );
        expect(validateStep(NestedWizardSteps.Guests, validHost(), machineTypes)).toEqual(
            {guests: "Add at least one guest."}
        );
        expect(validateStep(NestedWizardSteps.Review, validHost(), machineTypes).review).toMatch(/Guests/);
        expect(validateStep(NestedWizardSteps.Review, validHost({server_name: ""}), machineTypes).review)
            .toMatch(/Host/);
        expect(validateStep(NestedWizardSteps.Review, validHost({guests: [guest("kali", 40)]}), machineTypes))
            .toEqual({});
    });

    it("moves back freely and forward only through valid steps", () => {
        const empty = initialNestedWizardState();
        // Host (0) invalid: forward goes nowhere.
        expect(resolveNavigation(0, 1, empty, machineTypes)).toBe(0);
        expect(resolveNavigation(0, 4, empty, machineTypes)).toBe(0);
        // Host valid, no guests: jumping to Review stops at Guests (2).
        expect(resolveNavigation(0, 4, validHost(), machineTypes)).toBe(2);
        expect(resolveNavigation(0, 2, validHost(), machineTypes)).toBe(2);
        // Back is always allowed, even from a broken state.
        expect(resolveNavigation(3, 1, empty, machineTypes)).toBe(1);
        // A guest change that breaks the Host disk size sends a forward move back to Host.
        const broken = validHost({guests: [guest("kali", 40)], disk_size: 40});
        expect(resolveNavigation(3, 4, broken, machineTypes)).toBe(0);
    });
});
