import {useModal} from "mui-modal-provider";
import SimpleSnackbar from "../components/Common/SnackBar/SnackBar";

export const useClipboard = () => {
    const {showModal} = useModal();

    const copy = (content: any, message?: string) => {
        navigator.clipboard.writeText(content)
            .then(() => showModal(SimpleSnackbar, {
                message: message ? message : "Copied to clipboard"
            }))
            .catch(() => {
                showModal(SimpleSnackbar, {message: "Failed to copy to clipboard"})
            });
    }

    return {copy}
}