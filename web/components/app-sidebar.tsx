"use client"

import * as React from "react"
import {
  Rabbit,
  LayoutDashboard,
  FolderGit2,
  GitPullRequest,
  Brain,
  Settings,
  BookOpen,
} from "lucide-react"

import { NavMain } from "@/components/nav-main"
import { NavProjects } from "@/components/nav-projects"
import { NavUser } from "@/components/nav-user"
import { TeamSwitcher } from "@/components/team-switcher"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from "@/components/ui/sidebar"

const data = {
  user: {
    name: "User",
    email: "user@example.com",
    avatar: "/avatars/default.jpg",
  },
  teams: [
    {
      name: "Open Rabbit",
      logo: Rabbit,
      plan: "Open Source",
    },
  ],
  navMain: [
    {
      title: "Dashboard",
      url: "/dashboard",
      icon: LayoutDashboard,
      isActive: true,
    },
    {
      title: "Repositories",
      url: "/dashboard/repositories",
      icon: FolderGit2,
      items: [
        {
          title: "All Repos",
          url: "/dashboard/repositories",
        },
        {
          title: "Connect New",
          url: "/dashboard/repositories/connect",
        },
      ],
    },
    {
      title: "Reviews",
      url: "/dashboard/reviews",
      icon: GitPullRequest,
      items: [
        {
          title: "Active",
          url: "/dashboard/reviews?status=active",
        },
        {
          title: "Completed",
          url: "/dashboard/reviews?status=completed",
        },
        {
          title: "History",
          url: "/dashboard/reviews/history",
        },
      ],
    },
    {
      title: "Knowledge Base",
      url: "/dashboard/knowledge",
      icon: Brain,
    },
    {
      title: "Documentation",
      url: "/docs",
      icon: BookOpen,
      items: [
        {
          title: "Getting Started",
          url: "/docs/getting-started",
        },
        {
          title: "GitHub App",
          url: "/docs/github-app",
        },
        {
          title: "API Reference",
          url: "/docs/api",
        },
      ],
    },
    {
      title: "Settings",
      url: "/dashboard/settings",
      icon: Settings,
      items: [
        {
          title: "Profile",
          url: "/dashboard/settings/profile",
        },
        {
          title: "GitHub App",
          url: "/dashboard/settings/github",
        },
        {
          title: "API Keys",
          url: "/dashboard/settings/api-keys",
        },
      ],
    },
  ],
  projects: [
    {
      name: "Recent Reviews",
      url: "/dashboard/reviews",
      icon: GitPullRequest,
    },
  ],
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <TeamSwitcher teams={data.teams} />
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={data.navMain} />
        <NavProjects projects={data.projects} />
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={data.user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
