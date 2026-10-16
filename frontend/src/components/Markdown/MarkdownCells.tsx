import { Cell, map } from '@mdxeditor/gurx';

// Define a cell to hold the Markdown content
const markdown$ = Cell<string>('');

// Define a signal to transform the images by adding sizes
const transformedMarkdown$ = Cell<string>(
    '',
    (realm) => {
        realm.link(
            realm.pipe(
                markdown$,
                map((content) =>
                    content.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, altText, imageUrl) => {
                        return `<img src="${imageUrl}" alt="${altText}" width="500" height="300" style="max-width: 100%; height: auto;" />`;
                    })
                )
            ),
            transformedMarkdown$
        );
    }
);

export { markdown$, transformedMarkdown$ };