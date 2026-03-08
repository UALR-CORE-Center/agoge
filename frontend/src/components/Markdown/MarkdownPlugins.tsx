import React from 'react';
import {
    AdmonitionDirectiveDescriptor,
    codeBlockPlugin,
    codeMirrorPlugin,
    diffSourcePlugin,
    directivesPlugin,
    headingsPlugin,
    imagePlugin,
    linkDialogPlugin,
    linkPlugin,
    listsPlugin,
    quotePlugin,
    tablePlugin,
    thematicBreakPlugin,
    toolbarPlugin,
    UndoRedo,
    BoldItalicUnderlineToggles,
    CreateLink,
    ListsToggle,
    BlockTypeSelect,
    InsertImage,
    InsertTable,
    InsertThematicBreak,
    DiffSourceToggleWrapper, markdownShortcutPlugin, InsertAdmonition,
} from "@mdxeditor/editor";


export interface GetEditorPluginsProps {
    oldContent?: string;
    imageUploadHandler: (file: File) => Promise<string>;
    defaultCodeBlockLanguage?: string;
}

/*
 * oldContent: What content is already in the file saved, if none it defaults to "Older version"
 * imageUploadHandler: Function that handles image uploads
 * defaultCodeBlockLanguage: What code language that will be defaulted in the editor
 * Returns: List of plugins that the editor will use EX: The toolbar and its plugins
 */
export const editorPlugins = ({
                                  oldContent = 'Older version',
                                  imageUploadHandler,
                                  defaultCodeBlockLanguage = 'python',
                              }: GetEditorPluginsProps) => {
    return [
        headingsPlugin(),
        linkPlugin(),
        quotePlugin(),
        linkDialogPlugin(),
        codeBlockPlugin({ defaultCodeBlockLanguage }),
        listsPlugin(),
        imagePlugin({ imageUploadHandler }),
        tablePlugin(),
        thematicBreakPlugin(),
        markdownShortcutPlugin(),
        codeMirrorPlugin({
            codeBlockLanguages: {
                js: 'JavaScript',
                python: 'Python',
                none: 'Bash',
                bash: 'Bash',
                powershell: 'PowerShell',
            },
        }),
        diffSourcePlugin({ diffMarkdown: oldContent, viewMode: 'rich-text', readOnlyDiff: true }),
        directivesPlugin({ directiveDescriptors: [AdmonitionDirectiveDescriptor] }),
        toolbarPlugin({
            toolbarContents: () => (
                <>
                    <DiffSourceToggleWrapper>
                        <BoldItalicUnderlineToggles />
                        <CreateLink />
                        <InsertThematicBreak />
                        <ListsToggle />
                        <BlockTypeSelect />
                        <InsertAdmonition />
                        <InsertImage />
                        <InsertTable />
                        <UndoRedo />
                    </DiffSourceToggleWrapper>
                </>
            ),
        }),
    ];
};

/*
 * oldContent: What content is already in the file saved, if none it defaults to "Older version"
 * imageUploadHandler: Function that handles image uploads
 * defaultCodeBlockLanguage: What code language that will be defaulted in the editor
 * Returns: List of plugins that the viewer will use to display the images, tables, etc
 */
export const viewerPlugins = ({
                                  oldContent = 'Older version',
                                  defaultCodeBlockLanguage = 'python',
                              }: { oldContent?: string; defaultCodeBlockLanguage?: string } = {}) => [
    headingsPlugin(),
    linkPlugin(),
    quotePlugin(),
    linkDialogPlugin(),
    codeBlockPlugin({ defaultCodeBlockLanguage }),
    listsPlugin(),
    imagePlugin(),
    tablePlugin(),
    thematicBreakPlugin(),
    codeMirrorPlugin({
        codeBlockLanguages: {
            js: 'JavaScript',
            python: 'Python',
            none: 'Bash',
            bash: 'Bash',
            powershell: 'PowerShell',
        },
    }),
    diffSourcePlugin({ diffMarkdown: oldContent, viewMode: 'rich-text' }),
    directivesPlugin({ directiveDescriptors: [AdmonitionDirectiveDescriptor] }),
];