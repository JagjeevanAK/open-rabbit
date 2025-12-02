# GitHub Copilot Instructions

## Documentation Generation
- Do not generate multiple summary .md files when completing agentic work unless an explicit request is made or feature is complex
<!-- - Consolidate documentation into a single, comprehensive file when necessary -->

## Code Comments
- Avoid writing comments for trivial or self-explanatory code
- Extra comments that a human wouldn't add or is inconsistent with the rest of the file
- Extra defensive checks or try/catch blocks that are abnormal for that area of the codebase (especially if called by trusted / validated codepaths)
- Casts to any to get around type issues
- Any other style that is inconsistent with the file
- Only add comments for complex logic that requires explanation
- Do not write comments for every function - let the code be self-documenting where possible
- Focus comments on the "why" rather than the "what" for complex implementations

## Code Style
- Do not use emojis in code, comments, or commit messages
- Keep code clean and professional
