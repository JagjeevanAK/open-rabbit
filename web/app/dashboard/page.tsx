"use client";

import { FolderGit2, GitPullRequest, Brain, Plus, ExternalLink } from "lucide-react";
import { AppSidebar } from "@/components/app-sidebar";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { StatsCard } from "@/components/dashboard/stats-card";
import { ActivityFeed, ReviewActivity } from "@/components/dashboard/activity-feed";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import Link from "next/link";

// Mock data for demonstration
const mockActivities: ReviewActivity[] = [
  {
    id: "1",
    repo: "open-rabbit/backend",
    prNumber: 42,
    prTitle: "Add new review agent with improved parsing",
    status: "completed",
    createdAt: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    completedAt: new Date(Date.now() - 1000 * 60 * 25).toISOString(),
  },
  {
    id: "2",
    repo: "open-rabbit/web",
    prNumber: 15,
    prTitle: "Implement dashboard UI components",
    status: "running",
    createdAt: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
  },
  {
    id: "3",
    repo: "open-rabbit/bot",
    prNumber: 8,
    prTitle: "Fix webhook authentication issue",
    status: "pending",
    createdAt: new Date(Date.now() - 1000 * 60 * 2).toISOString(),
  },
];

export default function DashboardPage() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
          <div className="flex items-center gap-2 px-4">
            <SidebarTrigger className="-ml-1" />
            <Separator
              orientation="vertical"
              className="mr-2 data-[orientation=vertical]:h-4"
            />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem>
                  <BreadcrumbPage>Dashboard</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>
        <div className="flex flex-1 flex-col gap-6 p-6 pt-0">
          {/* Stats Cards */}
          <div className="grid gap-4 md:grid-cols-3">
            <StatsCard
              title="Connected Repositories"
              value={3}
              description="from last month"
              icon={FolderGit2}
              trend={{ value: 12, isPositive: true }}
            />
            <StatsCard
              title="Reviews This Month"
              value={24}
              description="vs 18 last month"
              icon={GitPullRequest}
              trend={{ value: 33, isPositive: true }}
            />
            <StatsCard
              title="Knowledge Learnings"
              value={156}
              description="insights from feedback"
              icon={Brain}
            />
          </div>

          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
              <CardDescription>
                Get started with common tasks
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-3">
              <Button asChild>
                <Link href="/dashboard/repositories/connect">
                  <Plus className="mr-2 h-4 w-4" />
                  Connect Repository
                </Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href="/dashboard/reviews">
                  <GitPullRequest className="mr-2 h-4 w-4" />
                  View All Reviews
                </Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href="/docs/github-app">
                  <ExternalLink className="mr-2 h-4 w-4" />
                  Install GitHub App
                </Link>
              </Button>
            </CardContent>
          </Card>

          {/* Recent Activity */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Recent Reviews</CardTitle>
                  <CardDescription>
                    Latest code review activity across your repositories
                  </CardDescription>
                </div>
                <Button variant="ghost" size="sm" asChild>
                  <Link href="/dashboard/reviews">View all</Link>
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <ActivityFeed activities={mockActivities} />
            </CardContent>
          </Card>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
