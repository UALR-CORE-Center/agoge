import { useLocation } from 'react-router-dom';

export const ExtractSegment = (idx: number) => {
    const location = useLocation();

    const getSegment = (pathname: string): string => {
        const segments = pathname.split('/');
        if (idx in segments){
            return segments[idx];
        } else {
            return segments[segments.length - 1];
        }
    }
    return getSegment(location.pathname);
}
