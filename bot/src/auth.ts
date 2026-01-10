import axios from "axios";
import { Probot, Context } from "probot";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const AUTH_ENABLED = process.env.AUTH_ENABLED === "true";

export async function isAuthorized(owner: string, app: Probot): Promise<boolean> {
    if (!AUTH_ENABLED) {
        app.log.debug(`Auth disabled, allowing owner: ${owner}`);
        return true;
    }

    try {
        const response = await axios.get(`${BACKEND_URL}/users/check-owner/${owner}`);

        if (!response.data.authorized) {
            app.log.warn(`Unauthorized owner: ${owner} - not found in database`);
            return false;
        }

        app.log.info(`Authorized owner: ${owner}`);
        return true;

    } catch (error: any) {
        app.log.error(`Error checking owner authorization for ${owner}: ${error.message || error}`);
        return true;
    }
}


export async function postUnauthorizedComment(
    context: Context<"pull_request">,
    owner: string
): Promise<void> {
    await context.octokit.issues.createComment({
        owner: context.payload.repository.owner.login,
        repo: context.payload.repository.name,
        issue_number: context.payload.pull_request.number,
        body: `⚠️ **Unauthorized**: Owner "${owner}" is not registered. Please register for Open Rabbit to use this bot.`
    });
}

export default (app: Probot) => {
    app.log.info(`Auth module initialized (AUTH_ENABLED: ${AUTH_ENABLED})`);
};
