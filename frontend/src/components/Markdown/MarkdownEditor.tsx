import {MDXEditor} from '@mdxeditor/editor';
import '@mdxeditor/editor/style.css';
import '../../styles/mdDark.css'
import {Save} from "@mui/icons-material";
import LoadingButton from "@mui/lab/LoadingButton";
import {
    Box,
    Paper,
    Skeleton,
    Typography
} from "@mui/material";
import {useTheme} from "@mui/material/styles";
import {useModal} from 'mui-modal-provider';
import React, {useEffect, useState} from 'react';
import {useParams} from "react-router-dom";
import {Doc} from "../../services/Documents/docs.model";
import {docsService} from "../../services/Documents/docs.service";
import SimpleSnackbar from "../Common/SnackBar/SnackBar";
import {editorPlugins} from "./MarkdownPlugins";


const MarkdownEditor: React.FC = () => {
    const theme = useTheme();
    const {showModal} = useModal();

    const editorClassName = theme.palette.mode === 'dark' ? 'dark-theme dark-editor' : 'light-editor';
    const [file, setFile] = useState<Doc>();
    const [instructionType, setInstructionType] = useState<'student' | 'teacher'>('student');
    const [isLoadingSave, setIsLoadingSave] = useState(false);
    const [oldContent, setOldContent] = useState<string | null>(null);
    const [isLoadingImage, setIsLoadingImage] = useState<boolean>(false);
    const [isLoadingFile, setIsLoadingFile] = useState<boolean>(false);
    const {file_uid} = useParams<{ file_uid: string }>();

    const handleMarkdownChange = (newMarkdown: string) => {
        if (file) {
            setFile({ ...file, content: newMarkdown, instruction_type: instructionType });
        }
    };

    const handleSave = async () => {
        setIsLoadingSave(true);
        if(file){
            try {
                await docsService.save(
                    file.uid,
                    file.content || "",
                    file.instruction_type,
                    file.name
                );
                showModal(SimpleSnackbar, {
                    message: "File saved!",
                    severity: "success",
                    autoHideDuration: 3000
                });
            } catch (error) {
                setIsLoadingSave(false)
                console.error(error);
                showModal(SimpleSnackbar, {
                    message: `Save failed: ${error.message}`,
                    severity: "error",
                    autoHideDuration: 3000
                });
            } finally {
                setIsLoadingSave(false);
            }
        } else {
            setIsLoadingSave(false)
            showModal(SimpleSnackbar, {
                message: `Save failed with reason: file not provided!`,
                severity: "error",
                autoHideDuration: 3000
            });
        }
    };

    const imageUploadHandler = async (image: File): Promise<string> => {
        setIsLoadingImage(true);
        try {
            showModal(SimpleSnackbar, {
                message: `Uploading image ...`,
                severity: "info",
                autoHideDuration: 3000
            })
            const response = await docsService.post_image(image, instructionType);
            return response.image_url;
        } catch (error) {
            console.error('Error uploading image', error);
            showModal(SimpleSnackbar, {
                message: `Image upload failed: ${error.message}`,
                severity: "error",
            });
            throw error;
        } finally {
            setIsLoadingImage(false);
        }
    };

    useEffect(() => {
        const fetchFiles = async () =>{
            if (!file_uid) {
                setIsLoadingFile(false);
                return;
            }
            try {
                const fetchedFile = await docsService.get_instruction(file_uid);
                setFile(fetchedFile);
                if (fetchedFile.instruction_type === 'student' || fetchedFile.instruction_type === 'teacher') {
                    setInstructionType(fetchedFile.instruction_type);
                } else {
                    setInstructionType('student');
                }
            } catch (error) {
                console.error(error);
            } finally {
                setIsLoadingFile(false);
            }
        }
        fetchFiles();
    }, []);

    return (
        <Box sx={{ display: 'flex', height: '100%', mt: 10, justifyContent:'flex-center'}}>
            <Box component="main" sx={{ ml: 5 }}>
                {file && (
                    <Box
                        sx={{
                            display: 'flex',
                            alignItems: 'center',
                        }}
                    >
                        <Typography variant="h4">{file.name}</Typography>
                        {file && (
                            <LoadingButton
                                onClick={handleSave}
                                variant="contained"
                                color="success"
                                loading={isLoadingSave}
                                sx={{ml:2}}
                                endIcon={<Save />}
                            >
                                Save
                            </LoadingButton>
                        )}
                    </Box>
                )}
                <Paper
                    style={{
                        minHeight: "600px",
                        marginRight: "40px",
                        position: "relative",
                        width: '80vw'
                    }}
                >
                    {!file ? (
                        <Skeleton
                            variant="rectangular"
                            animation="wave"
                            style={{ width: "100%", minHeight: "600px" }}
                        />
                    ) : (
                        <MDXEditor
                            className={editorClassName}
                            key={`${file?.uid}`}
                            markdown={file?.content || ""}
                            onChange={handleMarkdownChange}
                            contentEditableClassName="prose"
                            plugins={editorPlugins({
                                oldContent: oldContent || "",
                                imageUploadHandler,
                            })}
                        />
                    )}
                </Paper>
            </Box>
        </Box>
    );
};

export default MarkdownEditor;