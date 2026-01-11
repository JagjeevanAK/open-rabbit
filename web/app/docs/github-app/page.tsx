import Link from "next/link";
import { Rabbit, ArrowLeft, Github, Key, Shield, Webhook, CheckCircle, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export default function GitHubAppPage() {
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
                <div className="mx-auto max-w-3xl">
                    {/* Header */}
                    <div className="mb-10">
                        <Badge variant="secondary" className="mb-4">Configuration</Badge>
                        <h1 className="text-3xl font-bold mb-4">GitHub App Setup</h1>
                        <p className="text-lg text-muted-foreground">
                            Create and configure a GitHub App to enable automated code reviews.
                        </p>
                    </div>

                    {/* Info Alert */}
                    <Alert className="mb-8">
                        <Github className="h-4 w-4" />
                        <AlertTitle>GitHub App Required</AlertTitle>
                        <AlertDescription>
                            Open Rabbit uses a GitHub App to access repositories and post review comments on pull requests.
                        </AlertDescription>
                    </Alert>

                    {/* Step 1: Create App */}
                    <section className="mb-8">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                                1
                            </div>
                            <h2 className="text-xl font-semibold">Create a GitHub App</h2>
                        </div>
                        <Card>
                            <CardContent className="pt-6 space-y-4">
                                <p className="text-sm text-muted-foreground">
                                    Go to your GitHub settings and create a new GitHub App:
                                </p>
                                <Button asChild>
                                    <a
                                        href="https://github.com/settings/apps/new"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                    >
                                        Create GitHub App
                                        <ExternalLink className="ml-2 h-4 w-4" />
                                    </a>
                                </Button>
                            </CardContent>
                        </Card>
                    </section>

                    {/* Step 2: Configure App */}
                    <section className="mb-8">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                                2
                            </div>
                            <h2 className="text-xl font-semibold">Configure App Settings</h2>
                        </div>
                        <Card>
                            <CardContent className="pt-6 space-y-4">
                                <div>
                                    <h4 className="font-medium mb-2">Basic Information</h4>
                                    <ul className="text-sm text-muted-foreground space-y-1">
                                        <li>• <strong>Name:</strong> Open Rabbit (or your preferred name)</li>
                                        <li>• <strong>Homepage URL:</strong> Your deployed URL</li>
                                        <li>• <strong>Webhook URL:</strong> <code className="bg-muted px-1 rounded">https://your-domain.com/api/webhook</code></li>
                                    </ul>
                                </div>
                            </CardContent>
                        </Card>
                    </section>

                    {/* Step 3: Permissions */}
                    <section className="mb-8">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                                3
                            </div>
                            <h2 className="text-xl font-semibold">Set Permissions</h2>
                        </div>
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base flex items-center gap-2">
                                    <Shield className="h-4 w-4" />
                                    Required Permissions
                                </CardTitle>
                                <CardDescription>
                                    Enable these repository permissions:
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="grid gap-3">
                                    {[
                                        { name: "Contents", access: "Read", desc: "Access repository code" },
                                        { name: "Pull requests", access: "Read & Write", desc: "Post review comments" },
                                        { name: "Issues", access: "Read & Write", desc: "Handle comments" },
                                        { name: "Metadata", access: "Read", desc: "Access repo info" },
                                    ].map((perm, i) => (
                                        <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                                            <div>
                                                <div className="font-medium text-sm">{perm.name}</div>
                                                <div className="text-xs text-muted-foreground">{perm.desc}</div>
                                            </div>
                                            <Badge variant="secondary">{perm.access}</Badge>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </section>

                    {/* Step 4: Subscribe to Events */}
                    <section className="mb-8">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                                4
                            </div>
                            <h2 className="text-xl font-semibold">Subscribe to Events</h2>
                        </div>
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base flex items-center gap-2">
                                    <Webhook className="h-4 w-4" />
                                    Webhook Events
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="flex flex-wrap gap-2">
                                    {[
                                        "Pull request",
                                        "Pull request review",
                                        "Pull request review comment",
                                        "Issue comment",
                                    ].map((event, i) => (
                                        <div key={i} className="flex items-center gap-1 text-sm">
                                            <CheckCircle className="h-3 w-3 text-green-500" />
                                            {event}
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </section>

                    {/* Step 5: Get Credentials */}
                    <section className="mb-8">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                                5
                            </div>
                            <h2 className="text-xl font-semibold">Get Credentials</h2>
                        </div>
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base flex items-center gap-2">
                                    <Key className="h-4 w-4" />
                                    Environment Variables
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <p className="text-sm text-muted-foreground mb-4">
                                    After creating the app, add these to your <code className="bg-muted px-1 rounded">bot/.env</code>:
                                </p>
                                <div className="bg-muted rounded-lg p-3 font-mono text-sm space-y-1">
                                    <div>APP_ID=your-app-id</div>
                                    <div>PRIVATE_KEY_PATH=./private-key.pem</div>
                                    <div>WEBHOOK_SECRET=your-webhook-secret</div>
                                </div>
                            </CardContent>
                        </Card>
                    </section>

                    {/* Step 6: Install */}
                    <section className="mb-10">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                                6
                            </div>
                            <h2 className="text-xl font-semibold">Install on Repositories</h2>
                        </div>
                        <Card className="border-green-500/50 bg-green-500/5">
                            <CardContent className="pt-6">
                                <p className="text-sm text-muted-foreground mb-4">
                                    Install your GitHub App on the repositories you want Open Rabbit to review.
                                    You can install on specific repos or all repos in an organization.
                                </p>
                                <div className="flex items-center gap-2 text-sm">
                                    <CheckCircle className="h-4 w-4 text-green-500" />
                                    <span>Open Rabbit will automatically review new pull requests!</span>
                                </div>
                            </CardContent>
                        </Card>
                    </section>

                    {/* Navigation */}
                    <div className="flex justify-between pt-6 border-t border-border">
                        <Button variant="outline" asChild>
                            <Link href="/docs/getting-started">
                                <ArrowLeft className="mr-2 h-4 w-4" />
                                Getting Started
                            </Link>
                        </Button>
                        <Button asChild>
                            <Link href="/docs/features">
                                Features
                            </Link>
                        </Button>
                    </div>
                </div>
            </main>
        </div>
    );
}
