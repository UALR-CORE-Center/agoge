import { Button, Snackbar } from "@mui/material";
import React, { useState } from "react";
import {useParams} from "react-router-dom";
import { useAuthContext } from "../../../context/AuthContext";
import { rubricService } from "../../../services/Rubric/rubric.service";

interface RubricGeneratorProps {
    buildId: string;
}

const RubricGenerator: React.FC<RubricGeneratorProps> = (props) => {
    const { firebaseUser } = useAuthContext();
    const [snackbarOpen, setSnackbarOpen] = useState(false);
    const { build_id } = useParams<{ build_id: string }>();

    const rubricParams = {
        id: props.buildId,
        total_points: 100,
        levels: ["Exemplary", "Proficient", "Developing", "Unsatisfactory"],
        categories: ["Configuration", "Documentation", "Communication", "Problem-solving"],
        criteria: [
            {
                description: "Configuration is fully complete, accurate, and optimized...",
                index: "0",
                category: "Configuration"
            }
        ],
        headers: ["Exemplary (20-25 pts)", "Proficient (14-19 pts)", "Developing (7-13 pts)", "Unsatisfactory (0-6 pts)"]
    };

    const generateRubricClick = async () => {
        if (!firebaseUser.user){
            console.log("firebaseUser is missing");
            return;
        }
        if (!build_id) {
            console.error("build_id is undefined");
            return;
        }
        console.log("Generating Rubric");
        try {
            await rubricService.generate_rubric(build_id, rubricParams);
            setSnackbarOpen(true);
        } catch (error) {
            console.error("Failed to generate rubric:", error);
        }
    };

    return (
        <div>
            <Button variant="contained" color="primary" onClick={generateRubricClick}>
                Generate Rubric
            </Button>
            <Snackbar
                open={snackbarOpen}
                onClose={() => setSnackbarOpen(false)}
                message="Rubric generated successfully!"
                autoHideDuration={3000}
            />
        </div>
    );
};

export default RubricGenerator;