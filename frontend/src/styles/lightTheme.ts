import {
    blue,
    blueGrey,
    green,
    red,
    yellow,
} from "@mui/material/colors";
import { createTheme, PaletteColorOptions } from "@mui/material/styles";
import {ThemeOptions} from "@mui/material/styles";

export const lightTheme: ThemeOptions = {
    palette: {
        mode: "light",
    },
}

export const theme =  createTheme({
   palette: {
       primary: {
           light: "#1c2538",
           main: "#1c2538",
           dark: "#1c2538"
       },
       secondary: {
           light: red[400],
           main: '#f50057',
           dark: red[800]
       },

   },
});