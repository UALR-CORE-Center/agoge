import {Add, Delete, ErrorOutline} from "@mui/icons-material";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Box, Button, Checkbox,
    Chip, Collapse, FormControlLabel,
    IconButton,
    ListItem, Paper,
    Stack,
    Typography,
    useTheme
} from "@mui/material";
import React, {useEffect, useMemo, useState} from "react";
import {TransitionGroup} from 'react-transition-group';

import {UseFormsHook} from "../../../../hooks/useForms";
import {EmptyListItem, EmptyListItemText} from "./Review/ReviewCommonStyles";
import {EditorFormFactory} from "./utils/EditorFormFactory";
import {
    CommonEditorChildrenProps,
    WebApplicationFormKeys
} from "./utils/EditorTypes";
import {
    FormFields,
    FormGroup, FormGroupOutline,
    FormTextField,
    StyledFormFieldLabel,
} from "./utils/FormFields";

interface Props extends CommonEditorChildrenProps {
    formHooks: UseFormsHook
}


const WebApplicationForm: React.FC<Props> = ({formHooks, disableForm, specification}: Props) => {
    const theme = useTheme();

    // default toggle first network service
    const [accordionStates, setAccordionStates] = useState<number[]>([0])


    const webAppNames = useMemo(() => {
        return formHooks.forms?.map(f => f[WebApplicationFormKeys.webAppName].value) || [];
    }, [formHooks.forms]);


    const webAppHostNames = useMemo(() => {
        return formHooks.forms?.map(f => f[WebApplicationFormKeys.webAppHostName].value) || [];
    }, [formHooks.forms]);


    const webAppStartingDir = useMemo(() => {
        return formHooks.forms?.map(f => f[WebApplicationFormKeys.webAppStartingDirectory].value) || [];
    }, [formHooks.forms]);


    useEffect(() => {
        validateUrlIsUnique();
    }, [JSON.stringify(webAppHostNames), JSON.stringify(webAppStartingDir)]);


    useEffect(() => {
        validateNameIsUnique();
    }, [JSON.stringify(webAppNames)]);


    const validateUrlIsUnique = () => {
        const processedUrls: string[] = [];
        const errors = [];
        const errorIndexes: number[] = [];
        for (const formIndex in formHooks.forms || []) {
            const form = formHooks.forms![formIndex];

            const hostFormField = form[WebApplicationFormKeys.webAppHostName];
            const directoryFormField = form[WebApplicationFormKeys.webAppStartingDirectory]

            const host = hostFormField.value;
            const path = directoryFormField.value;
            const fullUrl = host + path
            const errMsg = "Host Name and Starting Directory must be unique!";
            if (directoryFormField.error == null || directoryFormField.error == errMsg) {
                if (processedUrls.includes(fullUrl)) {
                    errors.push(errMsg);
                } else {
                    errors.push(null);
                }

                errorIndexes.push(parseInt(formIndex));
                processedUrls.push(fullUrl);
            }
        }

        formHooks.setErrors(WebApplicationFormKeys.webAppStartingDirectory, errors, errorIndexes);
    }


    const validateNameIsUnique = () => {
        const processedNames: string[] = [];
        const errors = [];
        const errorIndexes: number[] = [];
        for (const formIndex in formHooks.forms || []) {
            const form = formHooks.forms![formIndex];

            const appNameField = form[WebApplicationFormKeys.webAppName];
            const errMsg = "Name must be unique!";
            if (appNameField.error == null || appNameField.error == errMsg) {
                if (processedNames.includes(appNameField.value)) {
                    errors.push(errMsg);
                } else {
                    errors.push(null);
                }

                errorIndexes.push(parseInt(formIndex));
                processedNames.push(appNameField.value);
            }
        }

        formHooks.setErrors(WebApplicationFormKeys.webAppName, errors, errorIndexes);
    }

    const toggleAccordion = (index: number) => {
        if (accordionStates.includes(index)) {
            setAccordionStates(accordionStates.filter(idx => idx !== index));
        } else {
            setAccordionStates([...accordionStates, index]);
        }
    }

    const removeWebApp = (index: number) => {
        formHooks.removeForm(index);

        const indexOfIndex = accordionStates.findIndex(idx => idx == index)
        setAccordionStates(accordionStates.filter(idx => idx !== indexOfIndex));
    }

    const addWebApp = () => {
        formHooks.addForm(EditorFormFactory.generateWebAppForm())
        // Looks strange without .length - 1, but required to work
        setAccordionStates([formHooks.forms!.length])
    }

    return (
        <FormFields alignItems={'center'}>
            <TransitionGroup style={{width: '100%'}}>
                {
                    formHooks.forms?.map((networkServiceForm, index) => {
                        return (
                            <Collapse unmountOnExit key={index}>
                                <Accordion disableGutters expanded={accordionStates.includes(index)} key={index}>
                                    <AccordionSummary
                                        sx={{
                                            background: theme.palette.action.hover,
                                        }}

                                        onClick={() => toggleAccordion(index)}
                                        id={`web-application-panel-${index}-header`}
                                        aria-controls={`web-application-panel-${index}-content`}
                                        aria-expanded={accordionStates.includes(index)}
                                        aria-label={
                                            accordionStates.includes(index)
                                                ? `Collapse Web Application ${index}`
                                                : `Expand Web Application ${index}`
                                        }
                                    >
                                        <Stack width={'100%'} direction={'row'} alignItems={'center'}
                                               justifyContent={'space-between'}>
                                            <Stack direction={'row'} alignItems={'center'} gap={1}>
                                                <Typography variant={'h6'}>Web Application {index}</Typography>

                                                {
                                                    formHooks.doesFormHaveErrors(index) &&
                                                    <ErrorOutline role="img" color={'error'} fontSize={'small'} aria-label="This web application has validation errors"/>
                                                }
                                            </Stack>

                                            <IconButton
                                                disabled={disableForm}
                                                color={'error'}
                                                size={'small'}
                                                aria-label={`Delete Web Application ${index}`}
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    removeWebApp(index);
                                                }}
                                            >
                                                <Delete/>
                                            </IconButton>
                                        </Stack>
                                    </AccordionSummary>
                                    <AccordionDetails
                                        id={`web-application-panel-${index}-content`}
                                        aria-labelledby={`web-application-panel-${index}-header`}
                                    >
                                        <FormFields>
                                            <FormGroupOutline showOverlay={disableForm}> <FormGroup>
                                                <StyledFormFieldLabel>Name</StyledFormFieldLabel>
                                                <FormTextField
                                                    helpText={'Display name of the container'}
                                                    placeholder={'Example Application'}
                                                    formKey={WebApplicationFormKeys.webAppName}
                                                    disabled={disableForm}
                                                    fieldFn={(key) => formHooks.forms![index][key]}
                                                    onInputChange={(field, value) => {
                                                        formHooks.handleInputChange(field, value, index)
                                                    }}
                                                />
                                            </FormGroup>
                                            </FormGroupOutline>

                                            <FormGroupOutline showOverlay={disableForm}> <FormGroup>
                                                <StyledFormFieldLabel>Host Name</StyledFormFieldLabel>
                                                <FormTextField
                                                    helpText={'Host name for the URL'}
                                                    placeholder={'http://example-com'}
                                                    disabled={disableForm}
                                                    formKey={WebApplicationFormKeys.webAppHostName}
                                                    fieldFn={(key) => formHooks.forms![index][key]}
                                                    onInputChange={(field, value) => {
                                                        formHooks.handleInputChange(field, value, index)
                                                    }}
                                                />
                                            </FormGroup>
                                            </FormGroupOutline>

                                            <FormGroupOutline showOverlay={disableForm}> <FormGroup>
                                                <StyledFormFieldLabel>Starting Directory</StyledFormFieldLabel>
                                                <FormTextField
                                                    helpText={'The starting web directory for the container URL'}
                                                    formKey={WebApplicationFormKeys.webAppStartingDirectory}
                                                    disabled={disableForm}
                                                    fieldFn={(key) => formHooks.forms![index][key]}
                                                    onInputChange={(field, value) => {
                                                        formHooks.handleInputChange(field, value, index)
                                                    }}
                                                    placeholder={'/example'}
                                                />
                                            </FormGroup>
                                            </FormGroupOutline>
                                        </FormFields>
                                    </AccordionDetails>
                                </Accordion>
                            </Collapse>
                        )
                    })
                }

            </TransitionGroup>

            {
                formHooks.forms?.length == 0 &&
                <EmptyListItem sx={{padding: theme.spacing(2)}}>
                    <EmptyListItemText>
                        {specification.pending ?
                            'Loading...' : 'No Web Applications'
                        }
                    </EmptyListItemText>
                </EmptyListItem>
            }


            <Button disabled={disableForm} onClick={addWebApp} variant={'contained'}
                    sx={{width: '70%', backgroundColor:'secondary.dark'}} endIcon={<Add/>}>
                Add Web Application
            </Button>
        </FormFields>
    )
}

export default WebApplicationForm;