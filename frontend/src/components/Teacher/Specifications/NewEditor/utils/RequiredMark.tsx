import {Box} from "@mui/material";
import React from "react";

/**
 * Red asterisk placed after a required field's label. It is hidden from screen readers because the
 * input itself carries aria-required (pass `required` to the form field component).
 */
export const RequiredMark = () => (
    <Box component="span" aria-hidden="true" sx={{color: 'error.main', ml: 0.5}}>*</Box>
);
