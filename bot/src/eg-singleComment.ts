import { Probot } from "probot";

export default (app: Probot) => {
    app.on("pull_request.opened", async (context) => {
        await context.octokit.pulls.createReview({
            event: "COMMENT", 
            ...context.pullRequest(),
            comments: [{
            path: "package-lock.json",
            start_line: 13,
            start_side: "LEFT",
            // LEFT used to show only new code 
            // RIGHT used to show both old and new code
            line: 16,
            body: `
**🛠️ Refactor suggestion / ⚠️ Potential issues**

<details>
<summary>⚠️ Potential issue: Hardcoded localhost URLs</summary>

Replace hardcoded localhost URLs with environment variables:

\`\`\` diff
- href: 'http://localhost:3001/docs'
+ href: process.env.VITE_DOCS_URL || 'http://localhost:3001/docs'
- href: 'http://localhost:3001/blog'
+ href: process.env.VITE_BLOG_URL || 'http://localhost:3001/blog'
\`\`\`
</details>

<details>
<summary>🛠️ Refactor: Update placeholder repo URLs</summary>

\`\`\` suggestion
**[Zero Main Repository](https://github.com/Mail-0/Zero)** - The main Zero project  
**[Community Discussions](https://github.com/Mail-0/Zero/discussions)** - Join the conversation
\`\`\`
</details>

<details>
<summary>⚡ TypeScript / ESLint Suggestions</summary>

The \`this\` aliasing violates TypeScript/ESLint rules. Use arrow functions or bind to maintain proper scope:

\`\`\` diff
- const self = this;
- const syncSingleThread = (threadId: string) =>
+ const syncSingleThread = (threadId: string) =>
  Effect.gen(function* () {
    yield* Effect.sleep(500); // Rate limiting delay
-   return yield* withRetry(Effect.tryPromise(() => self.syncThread({ threadId })));
+   return yield* withRetry(Effect.tryPromise(() => this.syncThread({ threadId })));
  }).pipe(
    Effect.catchAll((error) => {
      console.error(\\\`Failed to sync thread \\\${threadId}:\\\`, error);
      return Effect.succeed(null);
    }),
- );
+ ).bind(this);
\`\`\`

Also consider whether swallowing all errors in \`syncSingleThread\` is appropriate.
</details>

<details>
<summary>🧰 Tools</summary>

<details>
<summary>🪛 GitHub Actions: autofix.ci</summary>
Automatically fixes linting and formatting issues.
</details>
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>
Use AI agents for code suggestion or refactoring guidance.
</details>
      `,
            }]
        });
    });
};
