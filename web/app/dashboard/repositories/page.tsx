"use client";

import { useState } from "react";
import Link from "next/link";
import { FolderGit2, Plus, Settings, Power, MoreHorizontal } from "lucide-react";

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
import { Switch } from "@/components/ui/switch";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";

interface Repository {
    id: string;
    name: string;
    owner: string;
    lastReview: string | null;
    reviewsCount: number;
    enabled: boolean;
}

// Mock data
const mockRepos: Repository[] = [
    { id: "1", name: "backend", owner: "open-rabbit", lastReview: new Date(Date.now() - 1000 * 60 * 30).toISOString(), reviewsCount: 42, enabled: true },
    { id: "2", name: "web", owner: "open-rabbit", lastReview: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), reviewsCount: 15, enabled: true },
    { id: "3", name: "bot", owner: "open-rabbit", lastReview: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(), reviewsCount: 8, enabled: true },
    { id: "4", name: "docs", owner: "open-rabbit", lastReview: null, reviewsCount: 0, enabled: false },
];

function formatTimeAgo(dateString: string | null): string {
    if (!dateString) return "Never";
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
    if (seconds < 60) return "just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

export default function RepositoriesPage() {
    const [repos, setRepos] = useState<Repository[]>(mockRepos);

    const toggleRepo = (id: string) => {
        setRepos(repos.map(repo => {
            if (repo.id === id) {
                const newEnabled = !repo.enabled;
                toast.success(newEnabled ? "Repository enabled" : "Repository disabled");
                return { ...repo, enabled: newEnabled };
            }
            return repo;
        }));
    };

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
                                    <BreadcrumbPage>Repositories</BreadcrumbPage>
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
                                        <FolderGit2 className="h-5 w-5" />
                                        Connected Repositories
                                    </CardTitle>
                                    <CardDescription>
                                        Manage which repositories Open Rabbit reviews
                                    </CardDescription>
                                </div>
                                <Button asChild>
                                    <Link href="/dashboard/repositories/connect">
                                        <Plus className="mr-2 h-4 w-4" />
                                        Connect Repository
                                    </Link>
                                </Button>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Repository</TableHead>
                                        <TableHead>Reviews</TableHead>
                                        <TableHead>Last Review</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Enabled</TableHead>
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {repos.length === 0 ? (
                                        <TableRow>
                                            <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                                                No repositories connected. Click &quot;Connect Repository&quot; to get started.
                                            </TableCell>
                                        </TableRow>
                                    ) : (
                                        repos.map((repo) => (
                                            <TableRow key={repo.id}>
                                                <TableCell className="font-medium">
                                                    <div className="flex items-center gap-2">
                                                        <FolderGit2 className="h-4 w-4 text-muted-foreground" />
                                                        {repo.owner}/{repo.name}
                                                    </div>
                                                </TableCell>
                                                <TableCell>{repo.reviewsCount}</TableCell>
                                                <TableCell className="text-muted-foreground">
                                                    {formatTimeAgo(repo.lastReview)}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant={repo.enabled ? "default" : "secondary"}>
                                                        {repo.enabled ? "Active" : "Paused"}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    <Switch
                                                        checked={repo.enabled}
                                                        onCheckedChange={() => toggleRepo(repo.id)}
                                                    />
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    <DropdownMenu>
                                                        <DropdownMenuTrigger asChild>
                                                            <Button variant="ghost" size="sm">
                                                                <MoreHorizontal className="h-4 w-4" />
                                                            </Button>
                                                        </DropdownMenuTrigger>
                                                        <DropdownMenuContent align="end">
                                                            <DropdownMenuItem>
                                                                <Settings className="mr-2 h-4 w-4" />
                                                                Settings
                                                            </DropdownMenuItem>
                                                            <DropdownMenuItem onClick={() => toggleRepo(repo.id)}>
                                                                <Power className="mr-2 h-4 w-4" />
                                                                {repo.enabled ? "Disable" : "Enable"}
                                                            </DropdownMenuItem>
                                                        </DropdownMenuContent>
                                                    </DropdownMenu>
                                                </TableCell>
                                            </TableRow>
                                        ))
                                    )}
                                </TableBody>
                            </Table>
                        </CardContent>
                    </Card>
                </div>
            </SidebarInset>
        </SidebarProvider>
    );
}
