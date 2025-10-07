import axios from "axios";
import { Probot, Context } from "probot";
import pullRequest from "./pullRequest.js";

const url = process.env.BACKEND_URL || "http://localhost:3000/"

export default (app: Probot) => {
    app.on(["pull_request.opened", "pull_request.synchronize"], async (context: Context<"pull_request">) => {
        const pr = context.payload.pull_request;
        const { owner, repo } = context.repo();

        const { data: files } = await context.octokit.pulls.listFiles({
            owner,
            repo,
            pull_number: pr.number,
        });

        const changedFiles = files.map((file) => ({
            filename: file.filename,
            status: file.status, // "added" | "removed" | "modified"
            additions: file.additions,
            deletions: file.deletions,
            changes: file.changes,
        }));

        try{
            await axios.post(url, { changedFiles, pr_no: pr.number, owner, repo});
            console.log(`Posted the changed files for ${pullRequest}`)
        } catch(err){
            console.error("Error while posting the changed file to server ",err)
        }
    });
};
