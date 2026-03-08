import {IFormFieldMeta} from "../../../../../types/Form";

export enum ServerFormKeys {
    serverName,
    serverBaseImage,
    serverSettingHide,
    serverSettingCommunity,
    serverSettingDeny,
    serverSettingsDiskSizeGb,
    serverSettingsMachineType,
    serverNetworks,
    serverNicNetwork,
    serverNicIPv4Addr,
    serverNicIpAliases,
    serverNicEnableExternalNat,
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
    [ServerFormKeys.serverEnableDirectConnections]: IFormFieldMeta;
}
