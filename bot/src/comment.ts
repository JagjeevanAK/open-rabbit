import { Probot } from "probot";

export default (app: Probot) => {
    app.on("pull_request.opened", async (context) => {
        await context.octokit.pulls.createReview({
            ...context.pullRequest(),
            event: "COMMENT", 
            body: `
**AI Review Summary**

- Found hardcoded localhost URLs → replace with env vars  
- Placeholder repo URLs need to be updated  

Here are the suggested changes:
    `,
    comments: [{
        path: "package-lock.json",
        line: 16,
        body: `
Potential issue: Hardcoded localhost

\`\`\`suggestion
href: process.env.VITE_DOCS_URL || 'http://localhost:3001/docs',
\`\`\`
        `,
    }, {
        path: "package-lock.json",
        line: 181,
        body: `
\`\`\`suggestion
href: process.env.VITE_BLOG_URL || 'http://localhost:3001/blog',
\`\`\`
        `,
    }, {
        path: "package.json",
        line: 19,
        body: `
Refactor: Update placeholder repo URLs

\`\`\`suggestion
**[Zero Main Repository](https://github.com/Mail-0/Zero)** - The main Zero project  
**[Community Discussions](https://github.com/Mail-0/Zero/discussions)** - Join the conversation  
\`\`\`
`,
    },{
                path: "package-lock.json",
                line: 16,
                body: `
Potential issue: Hardcoded localhost`
    }]
    });
})
};
