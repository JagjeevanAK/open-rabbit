import Link from "next/link";
import {
    Rabbit, ArrowLeft, GitPullRequest, Brain, Shield, Zap,
    Code2, MessageSquare, BarChart3, Terminal, CheckCircle
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const features = [
    {
        icon: GitPullRequest,
        title: "Automated PR Reviews",
        description: "Open Rabbit automatically reviews every pull request when opened or updated.",
        highlights: [
            "Instant feedback on code changes",
            "Line-by-line suggestions",
            "Summary of issues and improvements",
        ],
    },
    {
        icon: Code2,
        title: "Static Analysis",
        description: "Deep code analysis using AST parsing for accurate insights.",
        highlights: [
            "Bug detection",
            "Code complexity metrics",
            "Style consistency checks",
        ],
    },
    {
        icon: Shield,
        title: "Security Scanning",
        description: "Automatically detect security vulnerabilities and anti-patterns.",
        highlights: [
            "Secret detection",
            "SQL injection risks",
            "Dependency vulnerabilities",
        ],
    },
    {
        icon: Brain,
        title: "Learning System",
        description: "Improves over time based on your feedback.",
        highlights: [
            "React 👍/👎 to comments",
            "Knowledge base stores learnings",
            "Personalized to your codebase",
        ],
    },
    {
        icon: Terminal,
        title: "Unit Test Generation",
        description: "Generate test cases for your changed files.",
        highlights: [
            "Comment /create-unit-test",
            "Framework auto-detection",
            "Coverage improvement",
        ],
    },
    {
        icon: MessageSquare,
        title: "Manual Triggers",
        description: "Trigger reviews on-demand with simple commands.",
        highlights: [
            "/review - Trigger code review",
            "/create-unit-test - Generate tests",
            "Works in any PR comment",
        ],
    },
];

export default function FeaturesPage() {
    return (
        <div className="min-h-screen bg-background">
            {/* Navigation */}
            <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur">
                <nav className="container flex h-16 items-center justify-between px-4 md:px-8">
                    <Link href="/" className="flex items-center gap-2">
                        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
                            <Rabbit className="h-5 w-5 text-primary-foreground" />
                        </div>
                        <span className="text-xl font-bold">Open Rabbit</span>
                    </Link>

                    <Button variant="ghost" size="sm" asChild>
                        <Link href="/docs">
                            <ArrowLeft className="mr-2 h-4 w-4" />
                            Back to Docs
                        </Link>
                    </Button>
                </nav>
            </header>

            <main className="container px-4 md:px-8 py-12">
                <div className="mx-auto max-w-4xl">
                    {/* Header */}
                    <div className="mb-12 text-center">
                        <Badge variant="secondary" className="mb-4">Features</Badge>
                        <h1 className="text-3xl font-bold mb-4">What Open Rabbit Can Do</h1>
                        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                            A comprehensive AI-powered code review system with multi-agent architecture.
                        </p>
                    </div>

                    {/* Features Grid */}
                    <div className="grid md:grid-cols-2 gap-6 mb-12">
                        {features.map((feature, index) => (
                            <Card key={index} className="h-full">
                                <CardHeader>
                                    <div className="flex items-center gap-3">
                                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                            <feature.icon className="h-5 w-5" />
                                        </div>
                                        <CardTitle className="text-lg">{feature.title}</CardTitle>
                                    </div>
                                    <CardDescription>{feature.description}</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <ul className="space-y-2">
                                        {feature.highlights.map((highlight, i) => (
                                            <li key={i} className="flex items-center gap-2 text-sm">
                                                <CheckCircle className="h-3 w-3 text-green-500 shrink-0" />
                                                {highlight}
                                            </li>
                                        ))}
                                    </ul>
                                </CardContent>
                            </Card>
                        ))}
                    </div>

                    {/* Architecture */}
                    <Card className="mb-12">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <BarChart3 className="h-5 w-5" />
                                Multi-Agent Architecture
                            </CardTitle>
                            <CardDescription>
                                Open Rabbit uses specialized agents for comprehensive reviews
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="grid md:grid-cols-3 gap-4">
                                {[
                                    { name: "Supervisor", desc: "Orchestrates the review pipeline" },
                                    { name: "Parser Agent", desc: "AST analysis, security scanning" },
                                    { name: "Review Agent", desc: "LLM-powered code review" },
                                ].map((agent, i) => (
                                    <div key={i} className="p-4 rounded-lg bg-muted/50 text-center">
                                        <div className="font-medium text-sm mb-1">{agent.name}</div>
                                        <div className="text-xs text-muted-foreground">{agent.desc}</div>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Supported Languages */}
                    <Card className="mb-12">
                        <CardHeader>
                            <CardTitle>Supported Languages</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="flex flex-wrap gap-2">
                                {[
                                    "Python", "JavaScript", "TypeScript", "Go", "Rust",
                                    "Java", "C#", "C++", "Ruby", "PHP"
                                ].map((lang, i) => (
                                    <Badge key={i} variant="secondary">{lang}</Badge>
                                ))}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Navigation */}
                    <div className="flex justify-between pt-6 border-t border-border">
                        <Button variant="outline" asChild>
                            <Link href="/docs/github-app">
                                <ArrowLeft className="mr-2 h-4 w-4" />
                                GitHub App Setup
                            </Link>
                        </Button>
                        <Button asChild>
                            <Link href="/signup">
                                Get Started
                            </Link>
                        </Button>
                    </div>
                </div>
            </main>
        </div>
    );
}
