import Link from "next/link";
import { Rabbit, ArrowLeft, ArrowRight, Terminal, CheckCircle, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function GettingStartedPage() {
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
                        <Badge variant="secondary" className="mb-4">Getting Started</Badge>
                        <h1 className="text-3xl font-bold mb-4">Quick Start Guide</h1>
                        <p className="text-lg text-muted-foreground">
                            Get Open Rabbit running in under 5 minutes.
                        </p>
                    </div>

                    {/* Prerequisites */}
                    <section className="mb-10">
                        <h2 className="text-xl font-semibold mb-4">Prerequisites</h2>
                        <Card>
                            <CardContent className="pt-6">
                                <ul className="space-y-2">
                                    {[
                                        "Docker & Docker Compose",
                                        "Node.js 18+",
                                        "Python 3.11+ & UV",
                                        "GitHub Account",
                                    ].map((item, i) => (
                                        <li key={i} className="flex items-center gap-2 text-sm">
                                            <CheckCircle className="h-4 w-4 text-green-500" />
                                            {item}
                                        </li>
                                    ))}
                                </ul>
                            </CardContent>
                        </Card>
                    </section>

                    {/* Step 1 */}
                    <section className="mb-8">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                                1
                            </div>
                            <h2 className="text-xl font-semibold">Clone the Repository</h2>
                        </div>
                        <Card className="bg-muted/50">
                            <CardContent className="pt-4">
                                <div className="flex items-center justify-between bg-background rounded-lg p-3 font-mono text-sm">
                                    <code>git clone https://github.com/JagjeevanAK/open-rabbit.git</code>
                                    <Button variant="ghost" size="sm">
                                        <Copy className="h-4 w-4" />
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    </section>

                    {/* Step 2 */}
                    <section className="mb-8">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                                2
                            </div>
                            <h2 className="text-xl font-semibold">Start Infrastructure</h2>
                        </div>
                        <Card className="bg-muted/50">
                            <CardContent className="pt-4 space-y-3">
                                <p className="text-sm text-muted-foreground">
                                    Start PostgreSQL, Redis, and Elasticsearch:
                                </p>
                                <div className="bg-background rounded-lg p-3 font-mono text-sm">
                                    <code>docker compose up -d</code>
                                </div>
                            </CardContent>
                        </Card>
                    </section>

                    {/* Step 3 */}
                    <section className="mb-8">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                                3
                            </div>
                            <h2 className="text-xl font-semibold">Setup Backend</h2>
                        </div>
                        <Card className="bg-muted/50">
                            <CardContent className="pt-4 space-y-3">
                                <div className="bg-background rounded-lg p-3 font-mono text-sm space-y-1">
                                    <div><span className="text-muted-foreground"># Navigate to backend</span></div>
                                    <div>cd backend</div>
                                    <div><span className="text-muted-foreground"># Copy env file</span></div>
                                    <div>cp .env.example .env</div>
                                    <div><span className="text-muted-foreground"># Install dependencies</span></div>
                                    <div>uv sync</div>
                                    <div><span className="text-muted-foreground"># Run migrations</span></div>
                                    <div>uv run alembic upgrade head</div>
                                    <div><span className="text-muted-foreground"># Start server</span></div>
                                    <div>uv run uvicorn main:app --port 8080</div>
                                </div>
                            </CardContent>
                        </Card>
                    </section>

                    {/* Step 4 */}
                    <section className="mb-8">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                                4
                            </div>
                            <h2 className="text-xl font-semibold">Setup Bot</h2>
                        </div>
                        <Card className="bg-muted/50">
                            <CardContent className="pt-4 space-y-3">
                                <div className="bg-background rounded-lg p-3 font-mono text-sm space-y-1">
                                    <div><span className="text-muted-foreground"># In another terminal</span></div>
                                    <div>cd bot</div>
                                    <div>cp .env.example .env</div>
                                    <div>npm install</div>
                                    <div>npm start</div>
                                </div>
                            </CardContent>
                        </Card>
                    </section>

                    {/* Step 5 */}
                    <section className="mb-10">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                                5
                            </div>
                            <h2 className="text-xl font-semibold">Configure GitHub App</h2>
                        </div>
                        <Card className="bg-muted/50">
                            <CardContent className="pt-4">
                                <p className="text-sm text-muted-foreground mb-4">
                                    Create a GitHub App and configure credentials. See the detailed guide:
                                </p>
                                <Button asChild>
                                    <Link href="/docs/github-app">
                                        GitHub App Setup Guide
                                        <ArrowRight className="ml-2 h-4 w-4" />
                                    </Link>
                                </Button>
                            </CardContent>
                        </Card>
                    </section>

                    {/* Next Steps */}
                    <Card className="border-primary/50">
                        <CardHeader>
                            <CardTitle>You&apos;re Ready!</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <p className="text-sm text-muted-foreground mb-4">
                                Once configured, Open Rabbit will automatically review pull requests
                                in your connected repositories.
                            </p>
                            <div className="flex gap-3">
                                <Button asChild>
                                    <Link href="/docs/features">
                                        Explore Features
                                    </Link>
                                </Button>
                                <Button variant="outline" asChild>
                                    <Link href="/signup">
                                        Create Account
                                    </Link>
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </main>
        </div>
    );
}
