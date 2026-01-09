/**
 * Test Framework Detection and Test File Utilities
 * 
 * Detects test frameworks, finds existing test files, and suggests
 * test file paths following project conventions.
 */

import type { GitHubClient } from "../types/github.js";
import { getFileContent, listAllFiles } from "./githubCommit.js";

// Supported test frameworks
export type TestFramework = 
    | "vitest"
    | "jest"
    | "mocha"
    | "pytest"
    | "unittest"
    | "go-test"
    | "unknown";

export interface TestFrameworkInfo {
    framework: TestFramework;
    configFile?: string;
    testDirectory?: string;
    testFilePattern: RegExp;
    suggestedExtension: string;
}

// Test file patterns by framework
const TEST_PATTERNS: Record<TestFramework, RegExp> = {
    vitest: /\.(test|spec)\.(ts|tsx|js|jsx)$/,
    jest: /\.(test|spec)\.(ts|tsx|js|jsx)$/,
    mocha: /\.(test|spec)\.(ts|tsx|js|jsx)$/,
    pytest: /(^test_.*\.py$|_test\.py$)/,
    unittest: /(^test_.*\.py$|_test\.py$)/,
    "go-test": /_test\.go$/,
    unknown: /\.(test|spec)\.(ts|tsx|js|jsx)$|test_.*\.py$|_test\.py$|_test\.go$/,
};

// Config files that indicate a test framework
const FRAMEWORK_CONFIG_FILES: Record<string, TestFramework> = {
    "vitest.config.ts": "vitest",
    "vitest.config.js": "vitest",
    "vitest.config.mts": "vitest",
    "vite.config.ts": "vitest", // Often used with vitest
    "jest.config.ts": "jest",
    "jest.config.js": "jest",
    "jest.config.mjs": "jest",
    "jest.config.cjs": "jest",
    ".mocharc.json": "mocha",
    ".mocharc.js": "mocha",
    "mocha.opts": "mocha",
    "pytest.ini": "pytest",
    "pyproject.toml": "pytest", // Often contains pytest config
    "setup.cfg": "pytest",
    "conftest.py": "pytest",
};

// Common test directory names
const TEST_DIRECTORIES = [
    "__tests__",
    "tests",
    "test",
    "spec",
    "specs",
    "__test__",
];

/**
 * Detect the test framework used in a repository by checking config files.
 * 
 * @param octokit - Authenticated Octokit instance
 * @param owner - Repository owner
 * @param repo - Repository name
 * @param branch - Branch to check
 * @returns TestFrameworkInfo with detected framework and patterns
 */
export async function detectTestFramework(
    octokit: GitHubClient,
    owner: string,
    repo: string,
    branch: string
): Promise<TestFrameworkInfo> {
    // Check for framework config files
    for (const [configFile, framework] of Object.entries(FRAMEWORK_CONFIG_FILES)) {
        const content = await getFileContent(octokit, owner, repo, configFile, branch);
        if (content !== null) {
            // Special case: pyproject.toml might not have pytest config
            if (configFile === "pyproject.toml" && !content.includes("[tool.pytest")) {
                continue;
            }
            
            console.log(`[testDetector] Detected ${framework} from ${configFile}`);
            
            return {
                framework,
                configFile,
                testDirectory: await detectTestDirectory(octokit, owner, repo, branch, framework),
                testFilePattern: TEST_PATTERNS[framework],
                suggestedExtension: getSuggestedExtension(framework),
            };
        }
    }
    
    // Check package.json for test framework dependencies
    const packageJson = await getFileContent(octokit, owner, repo, "package.json", branch);
    if (packageJson) {
        try {
            const pkg = JSON.parse(packageJson);
            const allDeps = {
                ...pkg.dependencies,
                ...pkg.devDependencies,
            };
            
            if (allDeps.vitest) {
                return {
                    framework: "vitest",
                    testFilePattern: TEST_PATTERNS.vitest,
                    testDirectory: await detectTestDirectory(octokit, owner, repo, branch, "vitest"),
                    suggestedExtension: ".test.ts",
                };
            }
            
            if (allDeps.jest || allDeps["@jest/core"]) {
                return {
                    framework: "jest",
                    testFilePattern: TEST_PATTERNS.jest,
                    testDirectory: await detectTestDirectory(octokit, owner, repo, branch, "jest"),
                    suggestedExtension: ".test.ts",
                };
            }
            
            if (allDeps.mocha) {
                return {
                    framework: "mocha",
                    testFilePattern: TEST_PATTERNS.mocha,
                    testDirectory: await detectTestDirectory(octokit, owner, repo, branch, "mocha"),
                    suggestedExtension: ".test.ts",
                };
            }
        } catch (e) {
            console.log("[testDetector] Failed to parse package.json");
        }
    }
    
    // Fallback to unknown with generic patterns
    console.log("[testDetector] No test framework detected, using defaults");
    return {
        framework: "unknown",
        testFilePattern: TEST_PATTERNS.unknown,
        testDirectory: await detectTestDirectory(octokit, owner, repo, branch, "unknown"),
        suggestedExtension: ".test.ts",
    };
}

/**
 * Detect the test directory used in the project.
 */
async function detectTestDirectory(
    octokit: GitHubClient,
    owner: string,
    repo: string,
    branch: string,
    framework: TestFramework
): Promise<string | undefined> {
    // For Python, check common locations
    if (framework === "pytest" || framework === "unittest") {
        for (const dir of ["tests", "test"]) {
            try {
                const { data } = await octokit.repos.getContent({
                    owner,
                    repo,
                    path: dir,
                    ref: branch,
                });
                if (Array.isArray(data)) {
                    return dir;
                }
            } catch {
                // Directory doesn't exist
            }
        }
    }
    
    // For JS/TS frameworks
    for (const dir of TEST_DIRECTORIES) {
        try {
            const { data } = await octokit.repos.getContent({
                owner,
                repo,
                path: dir,
                ref: branch,
            });
            if (Array.isArray(data)) {
                return dir;
            }
        } catch {
            // Directory doesn't exist
        }
    }
    
    // Also check src/__tests__ pattern
    try {
        const { data } = await octokit.repos.getContent({
            owner,
            repo,
            path: "src/__tests__",
            ref: branch,
        });
        if (Array.isArray(data)) {
            return "src/__tests__";
        }
    } catch {
        // Directory doesn't exist
    }
    
    return undefined;
}

/**
 * Get suggested file extension based on framework.
 */
function getSuggestedExtension(framework: TestFramework): string {
    switch (framework) {
        case "vitest":
        case "jest":
        case "mocha":
            return ".test.ts";
        case "pytest":
        case "unittest":
            return "_test.py";
        case "go-test":
            return "_test.go";
        default:
            return ".test.ts";
    }
}

/**
 * Get all existing test files in the repository.
 * 
 * @param octokit - Authenticated Octokit instance
 * @param owner - Repository owner
 * @param repo - Repository name
 * @param branch - Branch to check
 * @returns Array of test file paths
 */
export async function getExistingTestFiles(
    octokit: GitHubClient,
    owner: string,
    repo: string,
    branch: string
): Promise<string[]> {
    const allFiles = await listAllFiles(octokit, owner, repo, branch);
    
    // Filter for test files using the generic pattern
    const testPattern = TEST_PATTERNS.unknown;
    const testFiles = allFiles.filter(file => testPattern.test(file));
    
    console.log(`[testDetector] Found ${testFiles.length} existing test files`);
    return testFiles;
}

/**
 * Check if a source file already has tests.
 * 
 * This checks for:
 * - Exact test file match (e.g., utils.ts -> utils.test.ts)
 * - Tests in __tests__ directory
 * - Tests in tests/ directory with same name
 * 
 * @param sourceFile - Path to the source file
 * @param testFiles - Array of existing test file paths
 * @returns true if tests exist for the source file
 */
export function hasExistingTests(sourceFile: string, testFiles: string[]): boolean {
    // Get base name without extension
    const baseName = getBaseName(sourceFile);
    const sourceDir = getDirName(sourceFile);
    
    // Patterns to check
    const possibleTestFiles = [
        // Same directory: file.ts -> file.test.ts, file.spec.ts
        `${sourceDir}/${baseName}.test.ts`,
        `${sourceDir}/${baseName}.test.tsx`,
        `${sourceDir}/${baseName}.test.js`,
        `${sourceDir}/${baseName}.test.jsx`,
        `${sourceDir}/${baseName}.spec.ts`,
        `${sourceDir}/${baseName}.spec.tsx`,
        `${sourceDir}/${baseName}.spec.js`,
        `${sourceDir}/${baseName}.spec.jsx`,
        
        // __tests__ directory (sibling)
        `${sourceDir}/__tests__/${baseName}.test.ts`,
        `${sourceDir}/__tests__/${baseName}.test.tsx`,
        `${sourceDir}/__tests__/${baseName}.test.js`,
        `${sourceDir}/__tests__/${baseName}.test.jsx`,
        `${sourceDir}/__tests__/${baseName}.ts`,
        `${sourceDir}/__tests__/${baseName}.tsx`,
        
        // Python style
        `${sourceDir}/test_${baseName}.py`,
        `${sourceDir}/${baseName}_test.py`,
        
        // tests/ directory at root or parallel to src
        `tests/${baseName}.test.ts`,
        `tests/${baseName}.test.js`,
        `test/${baseName}.test.ts`,
        `test/${baseName}.test.js`,
        `tests/test_${baseName}.py`,
        `tests/${baseName}_test.py`,
    ];
    
    // Normalize paths for comparison
    const normalizedTestFiles = testFiles.map(f => f.replace(/^\.\//, ""));
    
    for (const possiblePath of possibleTestFiles) {
        const normalized = possiblePath.replace(/^\.\//, "");
        if (normalizedTestFiles.includes(normalized)) {
            console.log(`[testDetector] Found existing test for ${sourceFile}: ${possiblePath}`);
            return true;
        }
    }
    
    // Also check if any test file contains the base name (for files like utils.ts -> utils.test.ts)
    for (const testFile of normalizedTestFiles) {
        const testBaseName = getBaseName(testFile);
        // Remove .test or .spec suffix to compare
        const cleanTestName = testBaseName.replace(/\.(test|spec)$/, "").replace(/^test_/, "").replace(/_test$/, "");
        if (cleanTestName === baseName) {
            console.log(`[testDetector] Found existing test for ${sourceFile}: ${testFile}`);
            return true;
        }
    }
    
    return false;
}

/**
 * Suggest a test file path for a given source file.
 * 
 * @param sourceFile - Path to the source file
 * @param frameworkInfo - Detected test framework info
 * @returns Suggested test file path
 */
export function suggestTestFilePath(
    sourceFile: string,
    frameworkInfo: TestFrameworkInfo
): string {
    const baseName = getBaseName(sourceFile);
    const sourceDir = getDirName(sourceFile);
    const ext = getExtension(sourceFile);
    
    // Python files
    if (ext === ".py") {
        if (frameworkInfo.testDirectory) {
            return `${frameworkInfo.testDirectory}/test_${baseName}.py`;
        }
        return `${sourceDir}/test_${baseName}.py`;
    }
    
    // Go files
    if (ext === ".go") {
        return `${sourceDir}/${baseName}_test.go`;
    }
    
    // JS/TS files
    const testExt = frameworkInfo.suggestedExtension;
    
    // If there's a dedicated test directory, use it
    if (frameworkInfo.testDirectory) {
        // For __tests__ in same directory
        if (frameworkInfo.testDirectory.includes("__tests__")) {
            return `${sourceDir}/__tests__/${baseName}${testExt}`;
        }
        // For separate tests/ directory
        return `${frameworkInfo.testDirectory}/${baseName}${testExt}`;
    }
    
    // Default: same directory with .test extension
    return `${sourceDir}/${baseName}${testExt}`;
}

/**
 * Filter files that should have tests generated.
 * 
 * Excludes:
 * - Test files themselves
 * - Config files
 * - Generated files
 * - Lock files
 * - Non-code files
 * 
 * @param files - Array of file paths
 * @returns Filtered array of testable files
 */
export function filterTestableFiles(files: string[]): string[] {
    const excludePatterns = [
        // Test files
        /\.(test|spec)\.(ts|tsx|js|jsx)$/,
        /test_.*\.py$/,
        /_test\.(py|go)$/,
        /__tests__\//,
        
        // Config files
        /\.(config|rc)\.(ts|js|json|yaml|yml)$/,
        /tsconfig.*\.json$/,
        /package\.json$/,
        /package-lock\.json$/,
        /yarn\.lock$/,
        /pnpm-lock\.yaml$/,
        /\.eslintrc/,
        /\.prettierrc/,
        /babel\.config/,
        /webpack\.config/,
        /vite\.config/,
        /vitest\.config/,
        /jest\.config/,
        
        // Non-code files
        /\.(md|txt|json|yaml|yml|toml|ini|env|gitignore|dockerignore)$/,
        /\.(png|jpg|jpeg|gif|svg|ico|webp)$/,
        /\.(css|scss|sass|less)$/,
        /\.(html|htm)$/,
        
        // Generated/build files
        /\/dist\//,
        /\/build\//,
        /\/node_modules\//,
        /\.d\.ts$/,
        /\.min\.(js|css)$/,
        
        // Lock and manifest files
        /requirements\.txt$/,
        /Pipfile\.lock$/,
        /poetry\.lock$/,
        /go\.sum$/,
        /go\.mod$/,
        /Cargo\.lock$/,
    ];
    
    return files.filter(file => {
        for (const pattern of excludePatterns) {
            if (pattern.test(file)) {
                return false;
            }
        }
        return true;
    });
}

// Utility functions

function getBaseName(filePath: string): string {
    const parts = filePath.split("/");
    const fileName = parts[parts.length - 1];
    // Remove extension
    const dotIndex = fileName.lastIndexOf(".");
    if (dotIndex > 0) {
        return fileName.substring(0, dotIndex);
    }
    return fileName;
}

function getDirName(filePath: string): string {
    const parts = filePath.split("/");
    if (parts.length > 1) {
        return parts.slice(0, -1).join("/");
    }
    return ".";
}

function getExtension(filePath: string): string {
    const parts = filePath.split("/");
    const fileName = parts[parts.length - 1];
    const dotIndex = fileName.lastIndexOf(".");
    if (dotIndex > 0) {
        return fileName.substring(dotIndex);
    }
    return "";
}
