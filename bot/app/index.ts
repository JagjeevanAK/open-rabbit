import { Probot } from "probot";
import { createNodeMiddleware } from "@octokit/webhooks";
import appFn from "../src/index"; 

export default async function handler(req: any, res: any) {
    const probot = new Probot({
        appId: process.env.APP_ID,
        privateKey: process.env.PRIVATE_KEY?.replace(/\\n/g, '\n'),
        secret: process.env.WEBHOOK_SECRET,
    });

    await probot.load(appFn);
    
    const middleware = createNodeMiddleware(probot.webhooks, { path: "/" });
    return middleware(req, res);
}
