import Link from "next/link";
import { Rabbit, ArrowLeft, BookOpen, Github, Zap, Shield, ArrowRight, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const docsSections = [
    {
        title: "Getting Started",
        description: "Quick start guide to set up Open Rabbit",
        icon: Zap,
        href: "/docs/getting-started",
    },
    {
        title: "GitHub App Setup",
        description: "Install and configure the GitHub App",
        icon: Github,
        href: "/docs/github-app",
    },
    {
        title: "Features",
        description: "Explore all Open Rabbit capabilities",
        icon: BookOpen,
        href: "/docs/features",
    },
];

export default function DocsPage() {
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

                    <div className="flex items-center gap-4">
                        <Badge variant="secondary">Docs</Badge>
                        <Button variant="ghost" size="sm" asChild>
                            <Link href="/">
                                <ArrowLeft className="mr-2 h-4 w-4" />
                                Back
                            </Link>
                        </Button>
                    </div>
                </nav>
            </header>

            <main className="container px-4 md:px-8 py-16">
                <div className="mx-auto max-w-4xl">
                    {/* Header */}
                    <div className="text-center mb-12">
                        <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-primary/10 mb-6">
                            <BookOpen className="h-8 w-8 text-primary" />
                        </div>
                        <h1 className="text-3xl md:text-4xl font-bold mb-4">Documentation</h1>
                        <p className="text-lg text-muted-foreground">
                            Everything you need to set up and use Open Rabbit.
                        </p>
                    </div>

                    {/* Quick Start */}
                    <Card className="mb-8 border-primary/50 bg-gradient-to-r from-primary/5 to-transparent">
                        <CardContent className="pt-6">
                            <div className="flex items-start gap-4">
                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                                    <Zap className="h-5 w-5" />
                                </div>
                                <div className="flex-1">
                                    <h3 className="font-semibold mb-1">Quick Start</h3>
                                    <p className="text-sm text-muted-foreground mb-3">
                                        Get up and running in under 5 minutes
                                    </p>
                                    <Button size="sm" asChild>
                                        <Link href="/docs/getting-started">
                                            Start Here
                                            <ArrowRight className="ml-2 h-4 w-4" />
                                        </Link>
                                    </Button>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Doc Sections */}
                    <div className="grid md:grid-cols-3 gap-6 mb-12">
                        {docsSections.map((section, index) => (
                            <Link key={index} href={section.href}>
                                <Card className="h-full hover:border-primary/50 transition-colors cursor-pointer">
                                    <CardHeader>
                                        <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                                            <section.icon className="h-5 w-5 text-muted-foreground" />
                                        </div>
                                        <CardTitle className="text-lg">{section.title}</CardTitle>
                                        <CardDescription>{section.description}</CardDescription>
                                    </CardHeader>
                                </Card>
                            </Link>
                        ))}
                    </div>

                    {/* What's Included */}
                    <div className="mb-12">
                        <h2 className="text-xl font-semibold mb-6">What&apos;s Covered</h2>
                        <div className="grid md:grid-cols-2 gap-3">
                            {[
                                "Installation & Setup",
                                "GitHub App Configuration",
                                "Automatic PR Reviews",
                                "Manual Review Triggers",
                                "Feedback & Learning System",
                                "Security & Privacy",
                            ].map((item, i) => (
                                <div key={i} className="flex items-center gap-2 text-sm">
                                    <CheckCircle className="h-4 w-4 text-green-500" />
                                    <span>{item}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* External Links */}
                    <div className="text-center border-t border-border pt-8">
                        <h2 className="text-lg font-semibold mb-4">Additional Resources</h2>
                        <div className="flex flex-wrap justify-center gap-4">
                            <Button variant="outline" asChild>
                                <a
                                    href="https://github.com/JagjeevanAK/open-rabbit"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                >
                                    <Github className="mr-2 h-4 w-4" />
                                    GitHub
                                </a>
                            </Button>
                            <Button variant="outline" asChild>
                                <a
                                    href="https://github.com/JagjeevanAK/open-rabbit/issues"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                >
                                    Report an Issue
                                </a>
                            </Button>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
