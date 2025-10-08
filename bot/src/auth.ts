import axios from "axios";
import { Probot } from "probot";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export default (app: Probot) => {
    app.on("pull_request.opened", async (context) => {
        const owner = context.payload.repository.owner.login;
        
        try {
            const response = await axios.get(`${BACKEND_URL}/users/check-owner/${owner}`);
            
            if (!response.data.authorized) {
                console.log(`Unauthorized owner: ${owner} - not found in database`);
                await context.octokit.issues.createComment({
                    owner: context.payload.repository.owner.login,
                    repo: context.payload.repository.name,
                    issue_number: context.payload.pull_request.number,
                    body: `Unauthorized: Owner "${owner}" is not registered. Please Register for open-rabbit.`
                });
                return;
            }
            
            console.log(`Authorized owner: ${owner}`);
            
        } catch (error) {
            console.error(`Error checking owner authorization:`, error);
        }
    });
};
