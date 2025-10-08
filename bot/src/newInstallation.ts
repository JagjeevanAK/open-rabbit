import axios from "axios";
import { Probot } from "probot";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export default (app: Probot) => {
    app.on("installation.created", async (context) => {
        const account = context.payload.installation.account.login;
        const accountType = context.payload.installation.account.type;
        console.log(`App installed by: ${account} (${accountType})`);

        try {
            const installData = {
                name: account,
                email: "",
                org: accountType === "Organization" ? account : "",
                sub: false
            };

            const response = await axios.post(
                `${BACKEND_URL}/users/new_install`,
                installData,
                {
                    headers: {
                        'Content-Type': 'application/json'
                    }
                }
            );

            console.log(`Successfully registered installation for ${account}:`, response.data);
        } catch (error) {
            if (axios.isAxiosError(error)) {
                console.error(`Failed to register installation for ${account}:`, error.response?.data || error.message);
            } else {
                console.error(`Unexpected error during installation registration:`, error);
            }
        }
    });
}
