export type DictionaryEntry = {
    [key: string]: string | number | boolean | null;
};

export type Dictionary = {
    [key: string]: DictionaryEntry;
};

export type ListOfDictionaries = DictionaryEntry[];
