"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, ChevronRight, Github, Rabbit, Settings2, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

const steps = [
    {
        id: 1,
        title: "Welcome",
        description: "Introduction to Open Rabbit",
    },
    {
        id: 2,
        title: "Install GitHub App",
        description: "Connect your repositories",
    },
    {
        id: 3,
        title: "Configure",
        description: "Set your preferences",
    },
    {
        id: 4,
        title: "Complete",
        description: "You're all set!",
    },
];

export default function OnboardingPage() {
    const router = useRouter();
    const [currentStep, setCurrentStep] = useState(1);
    const [settings, setSettings] = useState({
        autoReview: true,
        generateTests: false,
        learnFromFeedback: true,
    });

    const progress = (currentStep / steps.length) * 100;

    const handleNext = () => {
        if (currentStep < steps.length) {
            setCurrentStep(currentStep + 1);
        } else {
            toast.success("Setup complete! Welcome to Open Rabbit.");
            router.push("/dashboard");
        }
    };

    const handleBack = () => {
        if (currentStep > 1) {
            setCurrentStep(currentStep - 1);
        }
    };

    return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-background p-6">
            <div className="w-full max-w-2xl space-y-8">
                {/* Progress */}
                <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">
                            Step {currentStep} of {steps.length}
                        </span>
                        <span className="font-medium">{steps[currentStep - 1].title}</span>
                    </div>
                    <Progress value={progress} className="h-2" />
                </div>

                {/* Step Content */}
                <Card>
                    <CardHeader className="text-center">
                        {currentStep === 1 && (
                            <>
                                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary text-primary-foreground">
                                    <Rabbit className="h-8 w-8" />
                                </div>
                                <CardTitle className="text-2xl">Welcome to Open Rabbit</CardTitle>
                                <CardDescription className="text-base">
                                    AI-powered code reviews that learn from your feedback
                                </CardDescription>
                            </>
                        )}
                        {currentStep === 2 && (
                            <>
                                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                                    <Github className="h-8 w-8" />
                                </div>
                                <CardTitle className="text-2xl">Install GitHub App</CardTitle>
                                <CardDescription className="text-base">
                                    Connect Open Rabbit to your GitHub repositories
                                </CardDescription>
                            </>
                        )}
                        {currentStep === 3 && (
                            <>
                                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                                    <Settings2 className="h-8 w-8" />
                                </div>
                                <CardTitle className="text-2xl">Configure Preferences</CardTitle>
                                <CardDescription className="text-base">
                                    Customize how Open Rabbit reviews your code
                                </CardDescription>
                            </>
                        )}
                        {currentStep === 4 && (
                            <>
                                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-500 text-white">
                                    <Sparkles className="h-8 w-8" />
                                </div>
                                <CardTitle className="text-2xl">You&apos;re All Set!</CardTitle>
                                <CardDescription className="text-base">
                                    Open Rabbit is ready to review your pull requests
                                </CardDescription>
                            </>
                        )}
                    </CardHeader>
                    <CardContent className="space-y-6">
                        {currentStep === 1 && (
                            <div className="space-y-4 text-center">
                                <p className="text-muted-foreground">
                                    Open Rabbit automatically reviews your pull requests, providing actionable
                                    feedback and learning from your reactions to improve over time.
                                </p>
                                <div className="grid gap-3 text-left">
                                    {[
                                        "Automated code review on every PR",
                                        "Static analysis for bugs and security issues",
                                        "Learns from your feedback to improve suggestions",
                                        "Multi-language support",
                                    ].map((feature) => (
                                        <div key={feature} className="flex items-center gap-2">
                                            <Check className="h-4 w-4 text-green-500" />
                                            <span className="text-sm">{feature}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        {currentStep === 2 && (
                            <div className="space-y-4 text-center">
                                <p className="text-muted-foreground">
                                    Click the button below to install the Open Rabbit GitHub App. You&apos;ll be
                                    able to select which repositories to enable.
                                </p>
                                <Button size="lg" className="w-full" asChild>
                                    <a
                                        href="https://github.com/apps/open-rabbit"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                    >
                                        <Github className="mr-2 h-5 w-5" />
                                        Install GitHub App
                                    </a>
                                </Button>
                                <p className="text-xs text-muted-foreground">
                                    Already installed? Click next to continue.
                                </p>
                            </div>
                        )}
                        {currentStep === 3 && (
                            <div className="space-y-6">
                                <div className="flex items-center justify-between">
                                    <div className="space-y-0.5">
                                        <Label htmlFor="auto-review">Auto-review PRs</Label>
                                        <p className="text-sm text-muted-foreground">
                                            Automatically review new pull requests
                                        </p>
                                    </div>
                                    <Switch
                                        id="auto-review"
                                        checked={settings.autoReview}
                                        onCheckedChange={(checked) =>
                                            setSettings({ ...settings, autoReview: checked })
                                        }
                                    />
                                </div>
                                <div className="flex items-center justify-between">
                                    <div className="space-y-0.5">
                                        <Label htmlFor="generate-tests">Generate unit tests</Label>
                                        <p className="text-sm text-muted-foreground">
                                            Suggest unit tests for changed code
                                        </p>
                                    </div>
                                    <Switch
                                        id="generate-tests"
                                        checked={settings.generateTests}
                                        onCheckedChange={(checked) =>
                                            setSettings({ ...settings, generateTests: checked })
                                        }
                                    />
                                </div>
                                <div className="flex items-center justify-between">
                                    <div className="space-y-0.5">
                                        <Label htmlFor="learn-feedback">Learn from feedback</Label>
                                        <p className="text-sm text-muted-foreground">
                                            Improve suggestions based on your reactions
                                        </p>
                                    </div>
                                    <Switch
                                        id="learn-feedback"
                                        checked={settings.learnFromFeedback}
                                        onCheckedChange={(checked) =>
                                            setSettings({ ...settings, learnFromFeedback: checked })
                                        }
                                    />
                                </div>
                            </div>
                        )}
                        {currentStep === 4 && (
                            <div className="space-y-4 text-center">
                                <p className="text-muted-foreground">
                                    Open a pull request in any connected repository and Open Rabbit will
                                    automatically review it. Give feedback by reacting to comments!
                                </p>
                                <div className="rounded-lg bg-muted p-4">
                                    <code className="text-sm">/review</code>
                                    <p className="mt-2 text-xs text-muted-foreground">
                                        Comment this on any PR to trigger a manual review
                                    </p>
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Navigation */}
                <div className="flex justify-between">
                    <Button
                        variant="ghost"
                        onClick={handleBack}
                        disabled={currentStep === 1}
                    >
                        Back
                    </Button>
                    <Button onClick={handleNext}>
                        {currentStep === steps.length ? (
                            "Go to Dashboard"
                        ) : (
                            <>
                                Next
                                <ChevronRight className="ml-1 h-4 w-4" />
                            </>
                        )}
                    </Button>
                </div>
            </div>
        </div>
    );
}
