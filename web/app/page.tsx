import Link from "next/link";
import {
  Rabbit,
  GitPullRequest,
  Code2,
  Brain,
  Shield,
  Zap,
  ChevronRight,
  Github,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

// Platform icons as simple SVGs
const GitHubIcon = () => (
  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor">
    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
  </svg>
);

const GitLabIcon = () => (
  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor">
    <path d="M22.65 14.39L12 22.13 1.35 14.39a.84.84 0 0 1-.3-.94l1.22-3.78 2.44-7.51A.42.42 0 0 1 4.82 2a.43.43 0 0 1 .58 0 .42.42 0 0 1 .11.18l2.44 7.49h8.1l2.44-7.51A.42.42 0 0 1 18.6 2a.43.43 0 0 1 .58 0 .42.42 0 0 1 .11.18l2.44 7.51L23 13.45a.84.84 0 0 1-.35.94z" />
  </svg>
);

const BitbucketIcon = () => (
  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor">
    <path d="M.778 1.213a.768.768 0 0 0-.768.892l3.263 19.81c.084.5.515.868 1.022.873H19.95a.772.772 0 0 0 .77-.646l3.27-20.03a.768.768 0 0 0-.768-.891zM14.52 15.53H9.522L8.17 8.466h7.561z" />
  </svg>
);

const VSCodeIcon = () => (
  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor">
    <path d="M23.15 2.587L18.21.21a1.494 1.494 0 0 0-1.705.29l-9.46 8.63-4.12-3.128a.999.999 0 0 0-1.276.057L.327 7.261A1 1 0 0 0 .326 8.74L3.899 12 .326 15.26a1 1 0 0 0 .001 1.479L1.65 17.94a.999.999 0 0 0 1.276.057l4.12-3.128 9.46 8.63a1.492 1.492 0 0 0 1.704.29l4.942-2.377A1.5 1.5 0 0 0 24 20.06V3.939a1.5 1.5 0 0 0-.85-1.352zm-5.146 14.861L10.826 12l7.178-5.448v10.896z" />
  </svg>
);

const JetBrainsIcon = () => (
  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor">
    <path d="M0 0v24h24V0H0zm2.8 21.2h8V22h-8v-.8zM5.152 5.72l.752-.72 3.416 3.328L5.904 11.6l-.752-.72 2.584-2.592L5.152 5.72zm6.328 4.336H16V11.2h-4.52V10.056z" />
  </svg>
);

// Stats data
const stats = [
  { value: "10K+", label: "PRs Reviewed", description: "Weekly reviews processed" },
  { value: "89%", label: "Faster Merges", description: "Average time saved" },
  { value: "34%", label: "Fewer Bugs", description: "Regressions prevented" },
  { value: "87%", label: "AI Feedback", description: "Comments from AI" },
];

// Features data
const features = [
  {
    icon: GitPullRequest,
    title: "Automated PR Reviews",
    description: "Get instant, comprehensive code reviews on every pull request with actionable feedback.",
  },
  {
    icon: Brain,
    title: "Learns From Feedback",
    description: "Open Rabbit learns from your reactions to improve suggestions over time.",
  },
  {
    icon: Code2,
    title: "Multi-Language Support",
    description: "Supports Python, JavaScript, TypeScript, Go, Rust, and many more languages.",
  },
  {
    icon: Shield,
    title: "Security Analysis",
    description: "Automatically scans for vulnerabilities, secrets, and security anti-patterns.",
  },
  {
    icon: Zap,
    title: "Fast & Efficient",
    description: "Reviews complete in seconds, not minutes. No waiting for human reviewers.",
  },
  {
    icon: Github,
    title: "GitHub Native",
    description: "Seamlessly integrates with your existing GitHub workflow via GitHub App.",
  },
];

// How it works steps
const steps = [
  {
    number: "01",
    title: "Install GitHub App",
    description: "Connect Open Rabbit to your repositories in one click.",
  },
  {
    number: "02",
    title: "Open a Pull Request",
    description: "Create a PR as you normally would in any connected repo.",
  },
  {
    number: "03",
    title: "Get AI Review",
    description: "Open Rabbit analyzes your code and posts detailed feedback.",
  },
  {
    number: "04",
    title: "Merge with Confidence",
    description: "Address issues and merge knowing your code is reviewed.",
  },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <nav className="container flex h-16 items-center justify-between px-4 md:px-8">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
              <Rabbit className="h-5 w-5 text-primary-foreground" />
            </div>
            <span className="text-xl font-bold">Open Rabbit</span>
          </Link>

          <div className="hidden md:flex items-center gap-8">
            <Link href="/docs" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              Docs
            </Link>
            <Link href="https://github.com/JagjeevanAK/open-rabbit" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              GitHub
            </Link>
          </div>

          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/login">Sign in</Link>
            </Button>
            <Button size="sm" asChild>
              <Link href="/signup">
                Start Free
                <ChevronRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </nav>
      </header>

      <main>
        {/* Hero Section */}
        <section className="relative overflow-hidden">
          {/* Background gradient */}
          <div className="absolute inset-0 -z-10">
            <div className="absolute top-1/4 left-1/2 -translate-x-1/2 h-[500px] w-[800px] rounded-full bg-primary/20 blur-[128px]" />
          </div>

          <div className="container px-4 md:px-8 py-24 md:py-32">
            <div className="mx-auto max-w-4xl text-center">
              {/* Badge */}
              <Badge variant="secondary" className="mb-6 px-4 py-1.5">
                <span className="mr-2">🚀</span>
                Open Source AI Code Review
              </Badge>

              {/* Headline */}
              <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold tracking-tight mb-6">
                Ship high quality code.{" "}
                <span className="text-primary">Catch issues early.</span>
              </h1>

              {/* Subheadline */}
              <p className="text-lg md:text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
                AI-powered code reviews that learn from your feedback. Get actionable suggestions,
                security analysis, and automated testing—all from your pull requests.
              </p>

              {/* Platform badges */}
              <div className="flex flex-wrap items-center justify-center gap-4 mb-10 text-muted-foreground">
                <span className="text-sm">Available in</span>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-1.5 text-sm">
                    <GitHubIcon />
                    <span>GitHub</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-sm opacity-50">
                    <GitLabIcon />
                    <span>GitLab</span>
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0">Soon</Badge>
                  </div>
                  <div className="flex items-center gap-1.5 text-sm opacity-50">
                    <BitbucketIcon />
                    <span>Bitbucket</span>
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0">Soon</Badge>
                  </div>
                </div>
              </div>

              {/* CTA Buttons */}
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Button size="lg" className="h-12 px-8 text-base" asChild>
                  <Link href="/signup">
                    Start Free
                    <ArrowRight className="ml-2 h-5 w-5" />
                  </Link>
                </Button>
                <Button size="lg" variant="outline" className="h-12 px-8 text-base" asChild>
                  <Link href="https://github.com/JagjeevanAK/open-rabbit">
                    <Github className="mr-2 h-5 w-5" />
                    View on GitHub
                  </Link>
                </Button>
              </div>
            </div>
          </div>
        </section>

        {/* Stats Section */}
        <section className="border-y border-border/40 bg-muted/30">
          <div className="container px-4 md:px-8 py-16">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
              {stats.map((stat, index) => (
                <div key={index} className="text-center">
                  <div className="text-3xl md:text-4xl font-bold text-primary mb-1">
                    {stat.value}
                  </div>
                  <div className="text-sm font-medium mb-1">{stat.label}</div>
                  <div className="text-xs text-muted-foreground">{stat.description}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section className="container px-4 md:px-8 py-24">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Everything you need for better code reviews
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              Open Rabbit combines static analysis, AI-powered review, and continuous learning
              to help your team ship better code, faster.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, index) => (
              <div
                key={index}
                className="group relative rounded-2xl border border-border/50 bg-card p-6 transition-all hover:border-primary/50 hover:bg-card/80"
              >
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                  <feature.icon className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
                <p className="text-sm text-muted-foreground">{feature.description}</p>
              </div>
            ))}
          </div>
        </section>

        {/* How It Works Section */}
        <section className="bg-muted/30 border-y border-border/40">
          <div className="container px-4 md:px-8 py-24">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                How Open Rabbit works
              </h2>
              <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                Get started in minutes. No complex configuration required.
              </p>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
              {steps.map((step, index) => (
                <div
                  key={index}
                  className="relative rounded-2xl border border-border/50 bg-card p-6"
                >
                  <div className="text-5xl font-bold text-primary/20 mb-4">
                    {step.number}
                  </div>
                  <h3 className="text-lg font-semibold mb-2">{step.title}</h3>
                  <p className="text-sm text-muted-foreground">{step.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* IDE Section */}
        <section className="container px-4 md:px-8 py-24">
          <div className="text-center mb-12">
            <Badge variant="secondary" className="mb-4">Coming Soon</Badge>
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Also available in your IDE
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              Get code reviews as you write, right in your favorite editor.
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-8 text-muted-foreground">
            <div className="flex items-center gap-2 opacity-60">
              <VSCodeIcon />
              <span>VS Code</span>
            </div>
            <div className="flex items-center gap-2 opacity-60">
              <JetBrainsIcon />
              <span>JetBrains</span>
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="relative overflow-hidden">
          <div className="absolute inset-0 -z-10">
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 h-[400px] w-[600px] rounded-full bg-primary/20 blur-[128px]" />
          </div>

          <div className="container px-4 md:px-8 py-24">
            <div className="mx-auto max-w-3xl text-center">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Ready to improve your code reviews?
              </h2>
              <p className="text-lg text-muted-foreground mb-8">
                Join thousands of developers using Open Rabbit to ship better code, faster.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Button size="lg" className="h-12 px-8 text-base" asChild>
                  <Link href="/signup">
                    Start Free
                    <ArrowRight className="ml-2 h-5 w-5" />
                  </Link>
                </Button>
                <Button size="lg" variant="outline" className="h-12 px-8 text-base" asChild>
                  <Link href="/docs">
                    Read the Docs
                  </Link>
                </Button>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-border/40">
        <div className="container px-4 md:px-8 py-12">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
                <Rabbit className="h-4 w-4 text-primary-foreground" />
              </div>
              <span className="font-semibold">Open Rabbit</span>
            </div>

            <div className="flex items-center gap-6 text-sm text-muted-foreground">
              <Link href="/docs" className="hover:text-foreground transition-colors">Docs</Link>
              <Link href="https://github.com/JagjeevanAK/open-rabbit" className="hover:text-foreground transition-colors">GitHub</Link>
              <Link href="/docs/privacy" className="hover:text-foreground transition-colors">Privacy</Link>
              <Link href="/docs/terms" className="hover:text-foreground transition-colors">Terms</Link>
            </div>

            <div className="text-sm text-muted-foreground">
              © 2025 Open Rabbit. Open Source.
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
