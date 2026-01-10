"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { GitPullRequest, RefreshCw, ExternalLink, CheckCircle, Clock, XCircle, Loader2 } from "lucide-react";

import { AppSidebar } from "@/components/app-sidebar";
import {
    Breadcrumb,
    BreadcrumbItem,
    BreadcrumbLink,
    BreadcrumbList,
    BreadcrumbPage,
    BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
    SidebarInset,
    SidebarProvider,
    SidebarTrigger,
} from "@/components/ui/sidebar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface ReviewTask {
    task_id: string;
    status: string;
    created_at: string;
    completed_at?: string;
    repo?: string;
    pr_number?: number;
}

const statusConfig: Record<string, { icon: typeof Clock; label: string; variant: "default" | "secondary" | "destructive" }> = {
    pending: { icon: Clock, label: "Pending", variant: "secondary" },
    running: { icon: Loader2, label: "Running", variant: "default" },
    completed: { icon: CheckCircle, label: "Completed", variant: "default" },
    failed: { icon: XCircle, label: "Failed", variant: "destructive" },
};

// Mock data for demo
const mockReviews: ReviewTask[] = [
    { task_id: "abc-123", status: "completed", created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(), completed_at: new Date(Date.now() - 1000 * 60 * 25).toISOString(), repo: "open-rabbit/backend", pr_number: 42 },
    { task_id: "def-456", status: "running", created_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(), repo: "open-rabbit/web", pr_number: 15 },
    { task_id: "ghi-789", status: "pending", created_at: new Date(Date.now() - 1000 * 60 * 2).toISOString(), repo: "open-rabbit/bot", pr_number: 8 },
    { task_id: "jkl-012", status: "failed", created_at: new Date(Date.now() - 1000 * 60 * 60).toISOString(), completed_at: new Date(Date.now() - 1000 * 60 * 58).toISOString(), repo: "example/repo", pr_number: 123 },
];

function formatDate(dateString: string): string {
    return new Date(dateString).toLocaleString();
}

export default function ReviewsPage() {
    const [reviews, setReviews] = useState<ReviewTask[]>(mockReviews);
    const [isLoading, setIsLoading] = useState(false);
    const [activeTab, setActiveTab] = useState("all");

    const refreshReviews = async () => {
        setIsLoading(true);
        // In production, this would fetch from API
        await new Promise(resolve => setTimeout(resolve, 500));
        setReviews(mockReviews);
        setIsLoading(false);
    };

    const filteredReviews = reviews.filter(review => {
        if (activeTab === "all") return true;
        if (activeTab === "active") return ["pending", "running"].includes(review.status);
        if (activeTab === "completed") return review.status === "completed";
        return true;
    });

    return (
        <SidebarProvider>
            <AppSidebar />
            <SidebarInset>
                <header className="flex h-16 shrink-0 items-center gap-2">
                    <div className="flex items-center gap-2 px-4">
                        <SidebarTrigger className="-ml-1" />
                        <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
                        <Breadcrumb>
                            <BreadcrumbList>
                                <BreadcrumbItem>
                                    <BreadcrumbLink href="/dashboard">Dashboard</BreadcrumbLink>
                                </BreadcrumbItem>
                                <BreadcrumbSeparator />
                                <BreadcrumbItem>
                                    <BreadcrumbPage>Reviews</BreadcrumbPage>
                                </BreadcrumbItem>
                            </BreadcrumbList>
                        </Breadcrumb>
                    </div>
                </header>
                <div className="flex flex-1 flex-col gap-6 p-6 pt-0">
                    <Card>
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="flex items-center gap-2">
                                        <GitPullRequest className="h-5 w-5" />
                                        Review Tasks
                                    </CardTitle>
                                    <CardDescription>
                                        All code review tasks across your repositories
                                    </CardDescription>
                                </div>
                                <Button variant="outline" size="sm" onClick={refreshReviews} disabled={isLoading}>
                                    <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
                                    Refresh
                                </Button>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                                <TabsList>
                                    <TabsTrigger value="all">All</TabsTrigger>
                                    <TabsTrigger value="active">Active</TabsTrigger>
                                    <TabsTrigger value="completed">Completed</TabsTrigger>
                                </TabsList>
                                <TabsContent value={activeTab} className="mt-4">
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Repository</TableHead>
                                                <TableHead>PR</TableHead>
                                                <TableHead>Status</TableHead>
                                                <TableHead>Created</TableHead>
                                                <TableHead>Completed</TableHead>
                                                <TableHead className="text-right">Actions</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {filteredReviews.length === 0 ? (
                                                <TableRow>
                                                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                                                        No reviews found
                                                    </TableCell>
                                                </TableRow>
                                            ) : (
                                                filteredReviews.map((review) => {
                                                    const config = statusConfig[review.status] || statusConfig.pending;
                                                    const StatusIcon = config.icon;
                                                    return (
                                                        <TableRow key={review.task_id}>
                                                            <TableCell className="font-medium">{review.repo || "Unknown"}</TableCell>
                                                            <TableCell>#{review.pr_number || "—"}</TableCell>
                                                            <TableCell>
                                                                <Badge variant={config.variant} className="flex w-fit items-center gap-1">
                                                                    <StatusIcon className={`h-3 w-3 ${review.status === "running" ? "animate-spin" : ""} ${review.status === "completed" ? "text-green-500" : ""}`} />
                                                                    {config.label}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell className="text-muted-foreground text-sm">
                                                                {formatDate(review.created_at)}
                                                            </TableCell>
                                                            <TableCell className="text-muted-foreground text-sm">
                                                                {review.completed_at ? formatDate(review.completed_at) : "—"}
                                                            </TableCell>
                                                            <TableCell className="text-right">
                                                                <Button variant="ghost" size="sm" asChild>
                                                                    <Link href={`/dashboard/reviews/${review.task_id}`}>
                                                                        <ExternalLink className="h-4 w-4" />
                                                                    </Link>
                                                                </Button>
                                                            </TableCell>
                                                        </TableRow>
                                                    );
                                                })
                                            )}
                                        </TableBody>
                                    </Table>
                                </TabsContent>
                            </Tabs>
                        </CardContent>
                    </Card>
                </div>
            </SidebarInset>
        </SidebarProvider>
    );
}
