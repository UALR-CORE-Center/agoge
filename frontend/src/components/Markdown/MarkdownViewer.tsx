import {MDXEditor} from "@mdxeditor/editor";
import '@mdxeditor/editor/style.css';
import {Box, Paper, Skeleton, Typography} from "@mui/material";
import {useTheme} from "@mui/material/styles";
import React, {useEffect, useState} from "react";
import {useParams} from "react-router-dom";
import {Doc} from "../../services/Documents/docs.model";
import {docsService} from "../../services/Documents/docs.service";
import {viewerPlugins} from "./MarkdownPlugins";


const MarkdownViewer: React.FC = () => {
    const theme = useTheme();
    const editorClassName = theme.palette.mode === 'dark' ? 'dark-theme dark-editor' : 'light-editor';
    const { file_uid } = useParams<{ file_uid?: string }>();
    const [fileContent, setFileContent] = useState<Doc>();
    const instruction_type = "Student";

    useEffect(() =>{
        const fetchInstructions = async () =>{
            if (file_uid != null) {
                try{
                    setFileContent(await docsService.get_instruction(file_uid));
                } catch (error) {
                    console.error("Failed to fetch instructions...", error);
                }
            }
        }
        fetchInstructions();
    }, [file_uid]);

    return (
        <Box sx={{ display: 'flex', height: '100%', width: '100%', mt: 10, justifyContent: 'flex-center', flexDirection: 'column', alignItems: 'center' }}>
            {!fileContent ? (
                <Box sx={{pl:10, pr:10, width:'100%', height:'100%'}}>
                    <Skeleton
                        variant="rounded"
                        animation="wave"
                        sx={{ width: '100%', minHeight: '600px'}}
                    />
                </Box>
            ) : (
                <>
                    <Typography variant="h2" component="div" sx={{ flexGrow: 1 }}>
                        {fileContent?.name} instructions
                    </Typography>
                    <Box component="main" sx={{ pl: 10, pr: 10, width: '100%' }}>
                        <Paper style={{ width: '80vw', minHeight: '400px', overflow: 'hidden', marginRight: '40px', position: 'relative' }}>
                            <MDXEditor
                                className={editorClassName}
                                key={fileContent?.uid || "1"}
                                markdown={fileContent?.content || ""}
                                readOnly={true}
                                plugins={viewerPlugins()}
                            />
                        </Paper>
                    </Box>
                </>
            )}
        </Box>
    );
}

export default MarkdownViewer;