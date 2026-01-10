import { LucideIcon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatsCardProps {
    title: string;
    value: string | number;
    description?: string;
    icon: LucideIcon;
    trend?: {
        value: number;
        isPositive: boolean;
    };
    className?: string;
}

export function StatsCard({
    title,
    value,
    description,
    icon: Icon,
    trend,
    className,
}: StatsCardProps) {
    return (
        <Card className={cn("", className)}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{title}</CardTitle>
                <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
                <div className="text-2xl font-bold">{value}</div>
                {(description || trend) && (
                    <p className="text-xs text-muted-foreground">
                        {trend && (
                            <span
                                className={cn(
                                    "mr-1",
                                    trend.isPositive ? "text-green-500" : "text-red-500"
                                )}
                            >
                                {trend.isPositive ? "+" : "-"}{Math.abs(trend.value)}%
                            </span>
                        )}
                        {description}
                    </p>
                )}
            </CardContent>
        </Card>
    );
}
