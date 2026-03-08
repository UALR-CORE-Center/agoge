import {useEffect, useState} from "react";
import {AgogeImage} from "../../../../../services/Server/image.model";
import {Nic} from "../../../../../services/Specification/specification.model";
import {Server} from "../../../../../services/Specification/specificationEdit.model";
import {
    IServerForm,
    IServerFormField,
    IServerFormNetworks,
    IServerValidationFn,
    ServerFormKeys
} from "./ServerFormTypes";


export interface IUseServerForm {
    forms: IServerForm[]
    handleInitialization: (servers: Server[]) => void;

    addServer: () => void;
    removeServer: (idx: number) => void;

    handleServerValueChange: (k: keyof IServerForm, value: any, idx: number) => void;
    handleNicValueChange: (k: keyof IServerFormNetworks, value: any, serverIdx: number, nicIdx: number) => void;

    addNic: (serverIdx: number) => void;
    removeNic: (serverIdx: number, nicIdx: number) => void;


    hasErrors: () => boolean;
    doesServerHaveErrors: (serverIdx: number) => boolean;
    doesServerNetworkHaveErrors: (serverIdx: number) => boolean;
    doesNicHaveErrors: (nic: IServerFormNetworks) => boolean;

    validateNetworkAndServerNics: (networkLookup: { [key: string]: string }) => void;

    getField: (key: (keyof IServerForm | keyof IServerFormNetworks), serverIdx: number, nicIndex?: number) => IServerFormField
    isEmpty: () => boolean;

    render: (images: AgogeImage[]) => Server[];
}

export const useServerForm = ({rawData, initialize}: { rawData?: Server[], initialize: boolean }): IUseServerForm => {
    const [forms, setForms] = useState<IServerForm[]>([])

    useEffect(() => {
        if (initialize && !!rawData) {
            alert("Form initialized with null value")
        }

        if (initialize && rawData) {
            handleInitialization(rawData);
        }

    }, [initialize, rawData]);


    const handleInitialization = (servers: Server[] | null = null): void => {
        const initializedForms: IServerForm[] = [];
        for (const server of servers || []) {
            initializedForms.push(
                createServer(server)
            );
        }

        setForms(initializedForms);
    }


    const createServer = (server: Server | null = null): IServerForm => {
        const serverForm: IServerForm = {
            [ServerFormKeys.serverName]: {
                ...createDefaultFormFieldMeta(server?.name || '', [requiredValidator, serverNameValidator])
            },
            [ServerFormKeys.serverBaseImage]: {
                ...createDefaultFormFieldMeta(server?.image || '', [requiredValidator])
            },
            [ServerFormKeys.serverSettingHide]: {
                ...createDefaultFormFieldMeta(server?.hidden || false, [])
            },
            [ServerFormKeys.serverSettingsMachineType]: {
                ...createDefaultFormFieldMeta(server?.machine_type || '', [])
            },
            [ServerFormKeys.serverSettingsDiskSizeGb]: { // TODO: Add server disk size validator to enforce min size constraint
                ...createDefaultFormFieldMeta(server?.disk_size || 0, [])
            },
            [ServerFormKeys.serverSettingCommunity]: {
                ...createDefaultFormFieldMeta(server?.community_server || false, [])
            },
            [ServerFormKeys.serverSettingDeny]: {
                ...createDefaultFormFieldMeta(server?.tags?.includes("deny-outbound") || false, [])
            },
            [ServerFormKeys.serverNetworks]: []
        }

        for (const [key, value] of Object.entries(serverForm)) {
            if (!Array.isArray(value)) {
                validateFormField(key, value, serverForm, forms.length - 1, -1);
            }
        }


        let nicIdx = 0;
        for (const nic of (server?.nics || [])) {
            const formNic = createNetworkNicForm(nic);
            serverForm[ServerFormKeys.serverNetworks].push(formNic)

            validateNic(formNic, forms.length - 1, nicIdx, serverForm);
            nicIdx += 1;
        }

        return serverForm
    }

    const createNetworkNicForm = (nic: Nic | null = null): IServerFormNetworks => {
        return {
            [ServerFormKeys.serverNicNetwork]: {
                ...createDefaultFormFieldMeta(nic?.network || '', [requiredValidator])
            },
            [ServerFormKeys.serverNicIPv4Addr]: {
                // we're doing special validation below
                ...createDefaultFormFieldMeta(nic?.internal_ip || '', [])
            },
            [ServerFormKeys.serverNicIpAliases]: {
                ...createDefaultFormFieldMeta(nic?.ip_aliases?.join(',') || '', [serverNetworkIPAliasesValidator])
            },
            [ServerFormKeys.serverNicEnableExternalNat]: {
                ...createDefaultFormFieldMeta(nic?.external_nat || false, [])
            },
            [ServerFormKeys.serverEnableDirectConnections]: {
                ...createDefaultFormFieldMeta(nic?.direct_connect || false, [])
            },
        }
    }

    const removeServer = (formIndex: number) => {
        const copy = [...forms];
        copy.splice(formIndex, 1);
        setForms(copy);
    }

    const addServer = () => {
        const newServer = createServer()

        setForms([
            ...forms,
            newServer
        ]);
    }


    const isEmpty = () => {
        return forms.length == 0;
    }

    const validateFormField = (key: any, formField: IServerFormField, thisForm: IServerForm, serverIdx: number, nicIdx: number): void => {
        formField.error = null;
        for (const validatorFn of formField.validators) {
            formField.error = validatorFn(formField.value, key, thisForm, forms, serverIdx, nicIdx)
            if (formField.error !== null)
                break;
        }
    }


    const handleServerValueChange = (key: keyof IServerForm, value: string, idx: number) => {
        if (key !== ServerFormKeys.serverNetworks) {
            const copyOfForms = [...forms];
            const copy = {
                ...copyOfForms[idx],
                [key]: {
                    ...copyOfForms[idx][key],
                    value: value
                }
            }

            validateFormField(key, copy[key], forms[idx], idx, -1);
            copyOfForms[idx] = copy;
            setForms(copyOfForms)
        }
    }


    const handleNicValueChange = (key: keyof IServerFormNetworks, value: any, serverIdx: number, nicIdx: number) => {
        const copyOfForms = [...forms];
        const copy = {
            ...copyOfForms[serverIdx],
            [ServerFormKeys.serverNetworks]: [
                ...copyOfForms[serverIdx][ServerFormKeys.serverNetworks],
            ]
        }

        const copyOfNic: IServerFormNetworks = {
            ...copy[ServerFormKeys.serverNetworks][nicIdx],
            [key]: {
                ...copy[ServerFormKeys.serverNetworks][nicIdx][key],
                value: value
            }
        }

        // Direct Connections require External NAT
        if (key === ServerFormKeys.serverEnableDirectConnections) {
            copyOfNic[ServerFormKeys.serverNicEnableExternalNat] = {
                ...copyOfNic[ServerFormKeys.serverNicEnableExternalNat],
                value: true
            }
        }

        if (shouldValidateNicField(key)) {
            validateFormField(key, copyOfNic[key] as IServerFormField, forms[serverIdx], serverIdx, nicIdx);
        }


        copy[ServerFormKeys.serverNetworks][nicIdx] = copyOfNic;
        copyOfForms[serverIdx] = copy;
        setForms(copyOfForms)
    }


    const addNic = (serverIdx: number) => {
        const copyOfForms = [...forms];

        const newNic = createNetworkNicForm();
        copyOfForms[serverIdx] = {
            ...forms[serverIdx],
            [ServerFormKeys.serverNetworks]: [
                ...forms[serverIdx][ServerFormKeys.serverNetworks],
                newNic
            ]
        };

        const nicIdx = copyOfForms[serverIdx][ServerFormKeys.serverNetworks].length - 1;
        validateNic(newNic, serverIdx, nicIdx, copyOfForms[serverIdx])
        setForms(copyOfForms);
    }


    const validateNic = (nic: IServerFormNetworks, serverIdx: number, nicIdx: number, form: IServerForm) => {
        for (const [key, field] of Object.entries(nic)) {
            if (shouldValidateNicField(parseInt(key))) {
                validateFormField(key, field, forms[serverIdx], serverIdx, nicIdx);
            }
        }
    }


    const shouldValidateNicField = (key: ServerFormKeys): boolean => {
        // These fields are getting validated in validateNetworkAndServerNics
        const fieldsValidatedByBigValidator = [ServerFormKeys.serverNicIPv4Addr, ServerFormKeys.serverNicNetwork]
        return !fieldsValidatedByBigValidator.includes(key);
    }

    const removeNic = (serverIdx: number, nicIdx: number) => {
        const copyOfForms = [...forms];

        copyOfForms[serverIdx] = {
            ...forms[serverIdx],
            [ServerFormKeys.serverNetworks]:
                forms[serverIdx][ServerFormKeys.serverNetworks]
                    .filter((v, idx) => idx !== nicIdx)
        };

        setForms(copyOfForms);
    }


    const getField = (key: (keyof IServerForm | keyof IServerFormNetworks), serverIdx: number, nicIndex: number = -1): IServerFormField => {
        const level: IServerForm = forms[serverIdx];

        if (nicIndex >= 0) {
            return level[ServerFormKeys.serverNetworks][nicIndex][key as keyof IServerFormNetworks] as IServerFormField;
        }

        return level[key as keyof IServerForm] as IServerFormField;
    }


    const doesServerNetworkHaveErrors = (serverIndex: number): boolean => {
        const serverNetworks: IServerFormNetworks[] = forms[serverIndex][ServerFormKeys.serverNetworks];

        for (const nic of serverNetworks) {
            if (doesNicHaveErrors(nic)) {
                return true;
            }
        }

        return false;
    }


    const doesNicHaveErrors = (nic: IServerFormNetworks) => {
        for (const formField of Object.values(nic)) {
            if (!!formField.error) {
                return true;
            }
        }

        return false;
    }


    const createDefaultFormFieldMeta = (defaultValue: any, validators: IServerValidationFn[] = []): IServerFormField => ({
        value: defaultValue,
        error: null,
        initialized: false,
        validators: validators
    });


    const serverNameValidator = (v: string, k: keyof IServerForm, form: IServerForm, forms: IServerForm[], formIndex: number, nicIndex: number): string | null => {
        const pattern = /^[a-z](?!.*-$)[a-z0-9-]{0,52}$/;
        if (v?.trim() !== "")
            return pattern.test(v) ? null : "Name must start with a lowercase letter, can contain lowercase letters, numbers, and hyphens, must not end with a hyphen, and can be up to 52 characters long"

        return null;
    }

    const serverNetworkIPAliasesValidator = (v: string, k: keyof IServerForm, form: IServerForm, forms: IServerForm[], formIndex: number, nicIndex: number): string | null => {
        const addresses = v.replace(/\s/g, "").split(',');
        const processedAddresses: string[] = [];
        for (let addr of addresses) {
            let error;
            if ((error = ipAddressValidator(addr, k, form, forms, formIndex, nicIndex)) !== null) {
                return error;
            }
            if (processedAddresses.includes(addr)) {
                return 'No duplicates allowed!'
            }

            processedAddresses.push(addr)
        }

        return null;
    }

    const requiredValidator = (value: any, k: keyof IServerForm, form: IServerForm, forms: IServerForm[], formIndex: number, nicIndex: number): string | null => {
        if (!(!!value)) {
            return 'Required';
        }

        return null;
    }

    const ipAddressValidator = (v: string, k: keyof IServerForm, form: IServerForm, forms: IServerForm[], formIndex: number, nicIndex: number): string | null => {
        const pattern = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;
        if (v?.trim() !== "")
            return pattern.test(v) ? null : "Invalid IPv4 Address: " + v

        return null;
    }


    /**
     *
     * @param networkLookup Network Form Network -> Network Form Subnet,
     * @param network Server Network Name
     * @param ipAddress Server Network IP Address
     * @param allServerIPs
     */
    const serverNICValidator = (networkLookup: {
        [key: string]: string
    }, network: string, ipAddress: string, allServerIPs: string[]): string | null => {
        const hasDuplicates = () => {
            if (allServerIPs.includes(ipAddress)) {
                return `Address ${ipAddress} is already in use by another server or this server!`;
            }

            return null;
        }

        const isInSubnet = (ip: string, subnet: string) => {
            const ipToInteger = (ip: string) => ip.split('.').reduce((acc, octet) => (acc << 8) + parseInt(octet, 10), 0);
            const [subnetIP, maskLength] = subnet.split('/');
            const ipInteger = ipToInteger(ip);
            const subnetInteger = ipToInteger(subnetIP);
            const mask = ~((1 << (32 - parseInt(maskLength))) - 1); // Ensure mask length is parsed as an integer

            if ((ipInteger & mask) === (subnetInteger & mask)) {
                return null;
            }

            return `The IP address must be within the selected subnet: ${subnet}`
        }

        // This has been validated to exist at this point
        const subnet = networkLookup[network];

        let error
        if ((error = hasDuplicates()) !== null) {
            return error;
        } else if ((error = ipAddressValidator(ipAddress, ServerFormKeys.serverNicIPv4Addr as keyof IServerForm, {} as IServerForm, [], -1, -1)) !== null) {
            return error;
        } else if ((error = isInSubnet(ipAddress, subnet)) !== null) {
            return error;
        }

        return null;
    }

    const validateNetworkAndServerNics = (networkLookup: { [key: string]: string }): void => {
        // todo - this could be enhanced by introducing a debouncer on these fields
        // tread lightly... max depth can happen in here....
        let wasChanged = false;
        const serverForms = [...forms];
        const ipsInUse: string[] = [];
        let networkFieldError = null;
        let ipFieldError = null;
        for (const serverFormIndex in serverForms) {
            const copyOfServerForm: IServerForm = {...serverForms[serverFormIndex]};
            for (const nicIdx in copyOfServerForm[ServerFormKeys.serverNetworks]) {
                const copyOfNic = {...copyOfServerForm[ServerFormKeys.serverNetworks][nicIdx]}

                const networkField = copyOfNic[ServerFormKeys.serverNicNetwork];
                const ipField = copyOfNic[ServerFormKeys.serverNicIPv4Addr];

                if (!Object.keys(networkLookup).includes(networkField.value)) {
                    networkFieldError = "Network is not defined in Networks";
                } else {
                    networkFieldError = null;
                    ipFieldError = serverNICValidator(networkLookup, networkField.value, ipField.value, ipsInUse);
                }

                if (networkFieldError != networkField.error || ipFieldError != ipField.error) {
                    networkField.error = networkFieldError;
                    ipField.error = ipFieldError
                    wasChanged = true;
                }

                ipsInUse.push(ipField.value);
            }
        }

        wasChanged && setForms(serverForms);
    }


    const render = (images: AgogeImage[]): Server[] => {
        const serverValues: Server[] = [];
        for (const form of forms!) {
            const image = images.find(img => img.image == form[ServerFormKeys.serverBaseImage].value);
            const serverValue: Server = {
                name: form[ServerFormKeys.serverName].value,
                image: form[ServerFormKeys.serverBaseImage].value,
                hidden: form[ServerFormKeys.serverSettingHide].value,
                community_server: form[ServerFormKeys.serverSettingCommunity].value,
                deny_outbound: form[ServerFormKeys.serverSettingDeny].value,
                disk_size: form[ServerFormKeys.serverSettingsDiskSizeGb].value,
                details: {
                    description: image?.description || '',
                    os: image?.os || '',
                    labels: image?.labels || []
                },
                tags: image?.tags || [],
                can_ip_forward: form[ServerFormKeys.serverSettingDeny].value,
                machine_type: form[ServerFormKeys.serverSettingsMachineType].value || image?.machine_type,
                human_interaction: image?.human_interaction ? image.human_interaction : [],
                nics: [],
            };

            for (const nic of form[ServerFormKeys.serverNetworks]) {
                serverValue.nics!.push(
                    {
                        network: nic[ServerFormKeys.serverNicNetwork].value,
                        internal_ip: nic[ServerFormKeys.serverNicIPv4Addr].value,
                        subnet_name: "default",
                        external_nat: nic[ServerFormKeys.serverNicEnableExternalNat].value,
                        ip_aliases: nic[ServerFormKeys.serverNicIpAliases].value,
                        direct_connect: nic[ServerFormKeys.serverEnableDirectConnections].value
                    }
                )
            }

            serverValues.push(serverValue);
        }

        return serverValues;
    }


    const doesServerHaveErrors = (serverIdx: number): boolean => {
        return (
            doesServerNetworkHaveErrors(serverIdx) ||
            Object.values(forms[serverIdx]).some((f) => 'error' in f && f.error)
        );
    };

    const hasErrors = () => {
        return forms.some((_, i) => doesServerHaveErrors(i));
    };

    return {
        forms,
        handleInitialization,
        addServer,
        removeServer,
        addNic,
        removeNic,
        handleNicValueChange,
        handleServerValueChange,
        isEmpty,
        getField,
        doesServerHaveErrors,
        doesServerNetworkHaveErrors,
        doesNicHaveErrors,
        validateNetworkAndServerNics,
        render,
        hasErrors
    }
}

