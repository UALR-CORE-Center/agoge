import React, {useEffect, useState} from "react";

import {AgogeImage} from "../../../../../services/Server/image.model";
import {ServerMachineTypes} from "../../../../../services/Specification/specificationEdit.model";
import InputTags from "../../../../Common/FormInputs/InputTags";
import NumberInputField from "../../../../Common/FormInputs/NumberInputField";
import TextAreaField from "../../../../Common/FormInputs/TextAreaField";
import {
    DiskSizeProps,
    FormFields,
    FormGroup,
    FormGroupOutline,
    IFormKeys,
    IServerForm,
    MachineTypeStates,
    StyledFormFieldLabel
} from "../FormFields";
import {SelectMachineTypeTable} from "../SelectMachineType/SelectMachineTypeTable";


interface Props {
    image: { pending: boolean, data: AgogeImage | null };
    imageForm: IServerForm;
    machineTypes: { pending: boolean; data: ServerMachineTypes[]; };
    disableForm: boolean;
    updateFormFn: (key: IFormKeys, value: any, index: number | null) => void;
}

export const ServerDetailsForm: React.FC<Props> = (props) => {
    const [initialized, setInitialized] = useState<boolean>(false);
    const [imageTags, setImageTags] = useState<string[]>([]);
    const [machineTypeStates, setMachineTypeStates] = useState<MachineTypeStates>();
    const [description, setDescription] = useState<{ value: string, error: string }>({
        error: "",
        value: ""
    });
    const [diskSize, setDiskSize] = useState<DiskSizeProps>({
        error: null,
        value: 10,
        min: 10,
        max: 250
    });

    useEffect(() => {
        if (!initialized && props.image.data) {
            initializeForm();
        }
    }, [props.image.data, initialized]);

    useEffect(() => {

    }, []);

    const setDiskDetails = () => {
        const image = props.image.data;
        const addDisk = image!.add_disk;

        if (addDisk) {
            // eslint-disable-next-line prefer-const
            let {min, value} = diskSize;
            min = parseInt(addDisk);

            const currentValue = value && (value >= min) ? value : min;
            setDiskSize((prevState) => (
                {...prevState, min: min, value: currentValue}
            ));
        }
    }

    const updateMachineTypeState = (updates: Partial<MachineTypeStates>) => {
        setMachineTypeStates((prevState) => (
            {...prevState, ...updates} as MachineTypeStates
        ));
    };


    const initializeForm = () => {
        const form = props.imageForm;
        setImageTags(props.image.data!.labels);
        setDescription((prevState) => {
            const description = form[IFormKeys.DESCRIPTION] || props.image.data?.description || ""
            return {...prevState, value: description};
        });
        updateMachineTypeState({machineType: form[IFormKeys.MACHINE_TYPE]});

        const currentDiskSize = form[IFormKeys.DISK_SIZE];
        if (currentDiskSize) {
            setDiskSize((prevState) => (
                {...prevState, value: Number(currentDiskSize)}
            ));
        }
        setDiskDetails();
        setInitialized(true);
    }

    const handleDiskChange = (event: React.FocusEvent<HTMLInputElement>) => {
        const newValue = +event.target.value;

        let errorMsg;
        if (!newValue) {
            errorMsg = "Disk size cannot be empty!"
            setDiskSize((prevState) => ({...prevState, error: errorMsg}));
            return;

        } else if (newValue < diskSize.min) {
            errorMsg = `Image disk cannot be smaller than current value ${diskSize.min}`;
        } else if (newValue > diskSize.max) {
            errorMsg = `Image disk size cannot exceed ${diskSize.max}`;
        }

        if (errorMsg) {
            setDiskSize((prevState) => ({...prevState, error: errorMsg}));
        } else {
            setDiskSize((prevState) => (
                {...prevState, value: newValue, error: ""}
            ));
            props.updateFormFn(IFormKeys.DISK_SIZE, newValue, null);
        }
    }

    const updateDescription = (event: React.ChangeEvent<HTMLInputElement>) => {
        const newValue = event.target.value;

        let errorMsg;
        const valueLength = newValue.length;
        if (valueLength > 200) {
            errorMsg = `Description cannot exceed 200 characters!`;
        } else if (valueLength === 0) {
            errorMsg = `Description cannot be empty!`;
        }

        if (errorMsg) {
            setDescription((prevState) => (
                {...prevState, error: errorMsg}
            ))
        } else {
            setDescription(() => (
                {error: "", value: newValue}
            ));
            props.updateFormFn(IFormKeys.DESCRIPTION, newValue, null);
        }
    }


    const handleMachineTypeSelect = (selectedRow: any) => {
        if (selectedRow) {
            updateMachineTypeState({
                selectedMachineTypeRow: selectedRow,
                selectedMachineTypeError: false,
                machineType: selectedRow.id,
            });
            props.updateFormFn(IFormKeys.MACHINE_TYPE, selectedRow.id, null);
        } else {
            updateMachineTypeState({
                selectedMachineTypeRow: null,
                selectedMachineTypeError: true,
                machineType: '',
            });
            props.updateFormFn(IFormKeys.MACHINE_TYPE, "", null);
        }
    }

    const handleServicesChange = (updatedServices: string[]) => {
        props.updateFormFn(IFormKeys.TAGS, updatedServices, null);
    }

    return (
        <>
            <FormFields alignItems={'center'}>
                <FormGroupOutline showOverlay={props.disableForm}>
                    <FormGroup>
                        <StyledFormFieldLabel>Description</StyledFormFieldLabel>
                        <TextAreaField
                            id={"description"}
                            helperText={
                                description?.error ||
                                "General description up to 200 characters of machine purpose, " +
                                "installed services, and/or configuration."
                            }
                            label={"description"}
                            name={"description"}
                            defaultValue={description.value}
                            disabled={props.disableForm}
                            maxLength={200}
                            required={true}
                            maxRows={4}
                            onInputChange={updateDescription}
                            error={!!description.error}
                        />
                    </FormGroup>
                    <FormGroup sx={{my: 2}}>
                        <SelectMachineTypeTable
                            loading={props.machineTypes.pending}
                            options={props.machineTypes.data}
                            onSelect={handleMachineTypeSelect}
                            formFields={props.imageForm}
                            hasError={!!machineTypeStates?.selectedMachineTypeError}
                        />
                    </FormGroup>
                    <FormGroup>
                        <StyledFormFieldLabel>Disk Size (Gb)</StyledFormFieldLabel>
                        <NumberInputField
                            min={diskSize.min}
                            max={diskSize.max}
                            value={diskSize.value}
                            helperText={
                                diskSize?.error ||
                                "Minimum instance size differs based on OS. " +
                                "For example, Windows servers require a minimum disk size of 50GB."
                            }
                            onBlur={handleDiskChange}
                        />
                    </FormGroup>
                    <FormGroup sx={{mt: 2}}>
                        <StyledFormFieldLabel>Image Tags</StyledFormFieldLabel>
                        <InputTags
                            id="imageTags"
                            name="services"
                            tagType={"tags"}
                            ariaLabel={"Image services input"}
                            helperText={
                                "Comma delimited list of services and functionality provided on this server"
                            }
                            required={false}
                            initialTags={imageTags}
                            onTagChanges={handleServicesChange}
                        />
                    </FormGroup>
                </FormGroupOutline>
            </FormFields>
        </>
    );
}