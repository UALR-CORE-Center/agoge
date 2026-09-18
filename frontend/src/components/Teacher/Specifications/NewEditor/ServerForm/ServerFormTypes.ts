import {IFormFieldMeta} from "../../../../../types/Form";

export enum ServerFormKeys {
    serverName,
    serverBaseImage,
    serverSettingHide,
    serverSettingCommunity,
    serverSettingWireGuardGateway,
    serverSettingCanIpForward,
    serverSettingDeny,
    serverSettingTags,
    serverStartupScript,
    serverRoutes,
    serverSettingsDiskSizeGb,
    serverSettingsMachineType,
    serverNetworks,
    serverNicNetwork,
    serverNicIPv4Addr,
    serverNicIpAliases,
    serverNicEnableExternalNat,
    serverNicExternalIpName,
    serverEnableDirectConnections,
}


export type IServerValidationFn = (
    v: any,
    k: number,
    form: IServerForm,
    forms: IServerForm[],
    formIndex: number,
    nicIndex: number
) => null | string;

export interface IServerFormField extends IFormFieldMeta {
    validators: IServerValidationFn[];
}

export interface IServerForm {
    [ServerFormKeys.serverName]: IServerFormField;
    [ServerFormKeys.serverBaseImage]: IServerFormField;
    [ServerFormKeys.serverSettingHide]: IServerFormField;
    [ServerFormKeys.serverSettingCommunity]: IServerFormField;
    [ServerFormKeys.serverSettingWireGuardGateway]: IServerFormField;
    [ServerFormKeys.serverSettingCanIpForward]: IServerFormField;
    [ServerFormKeys.serverSettingTags]: IServerFormField;
    [ServerFormKeys.serverStartupScript]: IServerFormField;
    [ServerFormKeys.serverRoutes]: IServerFormField;
    [ServerFormKeys.serverSettingsDiskSizeGb]: IServerFormField;
    [ServerFormKeys.serverSettingsMachineType]: IServerFormField;
    [ServerFormKeys.serverSettingDeny]: IServerFormField;
    [ServerFormKeys.serverNetworks]: IServerFormNetworks[];
}

export interface IServerFormNetworks {
    [ServerFormKeys.serverNicNetwork]: IFormFieldMeta;
    [ServerFormKeys.serverNicIPv4Addr]: IFormFieldMeta;
    [ServerFormKeys.serverNicIpAliases]: IFormFieldMeta;
    [ServerFormKeys.serverNicEnableExternalNat]: IFormFieldMeta;
    [ServerFormKeys.serverNicExternalIpName]: IFormFieldMeta;
    [ServerFormKeys.serverEnableDirectConnections]: IFormFieldMeta;
}
