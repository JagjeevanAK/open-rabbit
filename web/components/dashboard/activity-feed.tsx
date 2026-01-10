import { GitPullRequest, CheckCircle, Clock, XCircle, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ReviewActivity {
    id: string;
    repo: string;
    prNumber: number;
    prTitle: string;
    status: "pending" | "running" | "completed" | "failed";
    createdAt: string;
    completedAt?: string;
}

interface ActivityFeedProps {
    activities: ReviewActivity[];
    className?: string;
}

const statusConfig: Record<string, { icon: typeof Clock; label: string; variant: "default" | "secondary" | "destructive"; className?: string }> = {
    pending: {
        icon: Clock,
        label: "Pending",
        variant: "secondary",
    },
    running: {
        icon: Loader2,
        label: "Running",
        variant: "default",
        className: "animate-spin",
    },
    completed: {
        icon: CheckCircle,
        label: "Completed",
        variant: "default",
        className: "text-green-500",
    },
    failed: {
        icon: XCircle,
        label: "Failed",
        variant: "destructive",
    },
};

function formatTimeAgo(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (seconds < 60) return "just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

export function ActivityFeed({ activities, className }: ActivityFeedProps) {
    if (activities.length === 0) {
        return (
            <div className={cn("flex flex-col items-center justify-center py-8 text-center", className)}>
                <GitPullRequest className="h-12 w-12 text-muted-foreground/50" />
                <h3 className="mt-4 text-lg font-semibold">No reviews yet</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                    Reviews will appear here when you connect a repository and open a PR.
                </p>
            </div>
        );
    }

    return (
        <div className={cn("space-y-4", className)}>
            {activities.map((activity) => {
                const config = statusConfig[activity.status];
                const StatusIcon = config.icon;

                return (
                    <div
                        key={activity.id}
                        className="flex items-center gap-4 rounded-lg border p-4 transition-colors hover:bg-muted/50"
                    >
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
                            <GitPullRequest className="h-5 w-5 text-muted-foreground" />
                        </div>
                        <div className="flex-1 space-y-1">
                            <div className="flex items-center gap-2">
                                <span className="font-medium">{activity.repo}</span>
                                <span className="text-muted-foreground">#{activity.prNumber}</span>
                            </div>
                            <p className="text-sm text-muted-foreground line-clamp-1">
                                {activity.prTitle}
                            </p>
                        </div>
                        <div className="flex items-center gap-3">
                            <Badge variant={config.variant} className="flex items-center gap-1">
                                <StatusIcon className={cn("h-3 w-3", config.className)} />
                                {config.label}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                                {formatTimeAgo(activity.createdAt)}
                            </span>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

export type { ReviewActivity };
