import { Probot } from "probot";

export default (app: Probot) => {
    app.on("installation.created", async (context) => {
        const account = context.payload.installation.account.login;
        console.log(`App installed by: ${account}`);

    });
}

