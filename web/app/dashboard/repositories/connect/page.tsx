"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Github, Check, ExternalLink, ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import Link from "next/link";

export default function ConnectRepositoryPage() {
    const router = useRouter();
    const [showSuccessDialog, setShowSuccessDialog] = useState(false);

    const handleInstallComplete = () => {
        setShowSuccessDialog(true);
    };

    const handleConfirm = () => {
        toast.success("Repository connected successfully!");
        router.push("/dashboard/repositories");
    };

    return (
        <div className="flex min-h-screen flex-col bg-background">
            <header className="border-b">
                <div className="container flex h-16 items-center px-4">
                    <Button variant="ghost" asChild>
                        <Link href="/dashboard/repositories">
                            <ArrowLeft className="mr-2 h-4 w-4" />
                            Back to Repositories
                        </Link>
                    </Button>
                </div>
            </header>

            <main className="container flex-1 py-8">
                <div className="mx-auto max-w-2xl space-y-8">
                    <div className="text-center">
                        <h1 className="text-2xl font-bold">Connect a Repository</h1>
                        <p className="mt-2 text-muted-foreground">
                            Install the Open Rabbit GitHub App to enable code reviews
                        </p>
                    </div>

                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Github className="h-5 w-5" />
                                GitHub App Installation
                            </CardTitle>
                            <CardDescription>
                                The GitHub App allows Open Rabbit to access your repositories and post review comments.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <Alert>
                                <AlertTitle>Permissions Required</AlertTitle>
                                <AlertDescription>
                                    <ul className="mt-2 list-inside list-disc space-y-1 text-sm">
                                        <li>Read access to code and metadata</li>
                                        <li>Read and write access to pull requests</li>
                                        <li>Read and write access to issues (for comments)</li>
                                    </ul>
                                </AlertDescription>
                            </Alert>

                            <div className="space-y-4">
                                <h3 className="font-medium">Installation Steps:</h3>
                                <ol className="list-inside list-decimal space-y-3 text-sm text-muted-foreground">
                                    <li>Click the button below to go to GitHub</li>
                                    <li>Select the repositories you want to enable</li>
                                    <li>Click &quot;Install&quot; to grant permissions</li>
                                    <li>Return here to complete setup</li>
                                </ol>
                            </div>

                            <div className="flex flex-col gap-3">
                                <Button size="lg" className="w-full" asChild>
                                    <a
                                        href="https://github.com/apps/open-rabbit"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                    >
                                        <Github className="mr-2 h-5 w-5" />
                                        Install GitHub App
                                        <ExternalLink className="ml-2 h-4 w-4" />
                                    </a>
                                </Button>
                                <Button
                                    size="lg"
                                    variant="outline"
                                    className="w-full"
                                    onClick={handleInstallComplete}
                                >
                                    <Check className="mr-2 h-5 w-5" />
                                    I&apos;ve Installed the App
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    <p className="text-center text-sm text-muted-foreground">
                        Need help? Check out our{" "}
                        <Link href="/docs/github-app" className="underline hover:text-foreground">
                            installation guide
                        </Link>
                        .
                    </p>
                </div>
            </main>

            {/* Success Dialog */}
            <Dialog open={showSuccessDialog} onOpenChange={setShowSuccessDialog}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <Check className="h-5 w-5 text-green-500" />
                            Installation Complete
                        </DialogTitle>
                        <DialogDescription>
                            Your repositories are now connected to Open Rabbit. Code reviews will
                            automatically run on new pull requests.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShowSuccessDialog(false)}>
                            Cancel
                        </Button>
                        <Button onClick={handleConfirm}>
                            Go to Repositories
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
