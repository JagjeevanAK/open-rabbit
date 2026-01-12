import Link from "next/link";
import {
  GitPullRequest,
  Code2,
  Brain,
  Shield,
  ChevronRight,
  Github,
  ArrowRight,
  TrendingUp,
  Settings,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import Dither from '@/components/Dither';

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
    icon: Brain,
    title: "Learns From Feedback",
    description: "Open Rabbit learns from your reactions to improve suggestions over time. Accept or dismiss suggestions to fine-tune the AI to your team's coding style and preferences.",
    highlights: ["Personalized suggestions", "Team-wide learning", "Continuous improvement"],
  },
  {
    icon: GitPullRequest,
    title: "Automated PR Reviews",
    description: "Get instant, comprehensive code reviews on every pull request with actionable feedback.",
    highlights: ["Inline code suggestions", "Architecture recommendations", "Best practices enforcement"],
  },
  {
    icon: Shield,
    title: "Security Analysis",
    description: "Automatically scans for vulnerabilities, hardcoded secrets, SQL injection, XSS, and 100+ security anti-patterns.",
  },
  {
    icon: Code2,
    title: "Multi-Language Support",
    description: "Supports Python, JavaScript, TypeScript with framework-specific insights.",
  },
  {
    icon: Settings,
    title: "Custom Rules",
    description: "Define your own coding standards and team conventions. Create custom rules to enforce your project's specific requirements.",
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
      {/* Floating Pill Navbar */}
      <header className="fixed top-6 left-1/2 -translate-x-1/2 z-50">
        <nav className="flex items-center justify-between gap-120 px-6 py-3 rounded-full bg-black/40 backdrop-blur-xl border border-white/10">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 overflow-hidden">
              <img src="/rabbit.svg" alt="Open Rabbit Logo" className="h-full w-full object-cover" />
            </div>
            <span className="text-lg font-semibold text-white">Open Rabbit</span>
          </Link>

          <div className="flex items-center gap-4">
            <Link
              href="/login"
              className="text-sm text-white/80 hover:text-white transition-colors"
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="group flex items-center justify-center gap-0 px-4 py-2 bg-white text-black text-sm font-medium rounded-full hover:bg-white/90 hover:scale-105 transition-all duration-200"
            >
              Start Free
              <ArrowRight className="h-4 w-0 opacity-0 group-hover:w-4 group-hover:opacity-100 group-hover:ml-1 transition-all duration-200" />
            </Link>
          </div>
        </nav>
      </header>

      <main>
        {/* Hero Section */}
        <section className="relative z-0 overflow-hidden h-screen flex flex-col items-center justify-center pb-20">
          {/* Dither Background */}
          <div className="absolute inset-0 -z-10">
            <Dither
              waveColor={[0.5, 0.5, 0.5]}
              disableAnimation={false}
              enableMouseInteraction={false}
              mouseRadius={0.3}
              colorNum={4}
              waveAmplitude={0.3}
              waveFrequency={3}
              waveSpeed={0.05}
            />
            {/* Overlay gradient */}
            <div className="absolute top-1/4 left-1/2 -translate-x-1/2 h-[500px] w-[800px] rounded-full bg-primary/20 blur-[128px]" />
          </div>

          <div className="container mx-auto px-4 md:px-8 py-24 md:py-32 relative z-10">
            <div className="mx-auto max-w-4xl text-center">
              {/* Badge */}
              <Badge variant="secondary" className="mb-4 px-4 py-1.5">
                <TrendingUp className="mr-2 h-4 w-4" />
                Open Source AI Code Review
              </Badge>

              {/* Headline */}
              <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold tracking-tight mb-6">
                Ship high quality code,{" "}
                <span className="text-primary">Catch issues early.</span>
              </h1>

              {/* Subheadline */}
              <p className="text-lg md:text-xl text-foreground/80 mb-8 max-w-2xl mx-auto">
                Codebase-aware Al Code Reviews in your pull requests and IDE
              </p>

              {/* CTA Buttons */}
              <div className="flex items-center justify-center gap-4">
                <Link
                  href="/signup"
                  className="group flex items-center justify-center gap-0 px-8 py-3 bg-white text-black font-medium rounded-full hover:bg-white/90 hover:scale-105 transition-all duration-200"
                >
                  Get Started
                  <ArrowRight className="h-5 w-0 opacity-0 group-hover:w-5 group-hover:opacity-100 group-hover:ml-2 transition-all duration-200" />
                </Link>
                <Link
                  href="https://github.com/JagjeevanAK/open-rabbit"
                  className="px-8 py-3 border border-white/30 text-white/80 font-medium rounded-full hover:bg-white/10 hover:text-white transition-colors"
                >
                  View on GitHub
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* Stats Section */}
        <section className="border-y border-border/40 bg-muted/30">
          <div className="container mx-auto px-12 md:px-24 lg:px-32 py-16">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
              {stats.map((stat, index) => (
                <div key={index} className="text-center">
                  <div className="text-4xl md:text-5xl font-bold text-primary mb-2">
                    {stat.value}
                  </div>
                  <div className="text-base font-medium mb-1">{stat.label}</div>
                  <div className="text-sm text-muted-foreground">{stat.description}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section className="container mx-auto px-12 md:px-24 lg:px-32 py-24">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Everything you need for better code reviews
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              Open Rabbit combines static analysis, AI-powered review, and continuous learning
              to help your team ship better code, faster.
            </p>
          </div>

          {/* Bento Grid - 2 on top, 3 on bottom */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Top Row - 2 Large Cards */}
            {/* Card 1: Learns From Feedback */}
            <div className="group relative rounded-2xl border border-border/50 bg-card overflow-hidden transition-all hover:border-primary/50 lg:col-span-1 md:col-span-1">
              {/* Illustration Area */}
              <div className="h-48 bg-muted/30 flex items-center justify-center border-b border-border/30">
                <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                  <Brain className="h-10 w-10" />
                </div>
              </div>
              {/* Content */}
              <div className="p-6">
                <h3 className="text-2xl font-semibold mb-2">{features[0].title}</h3>
                <p className="text-base text-muted-foreground">{features[0].description}</p>
              </div>
            </div>

            {/* Card 2: Automated PR Reviews - spans 2 cols on lg */}
            <div className="group relative rounded-2xl border border-border/50 bg-card overflow-hidden transition-all hover:border-primary/50 lg:col-span-2 md:col-span-1">
              <div className="flex flex-col lg:flex-row h-full">
                {/* Illustration Area */}
                <div className="h-48 lg:h-auto lg:w-1/2 bg-muted/30 flex items-center justify-center border-b lg:border-b-0 lg:border-r border-border/30">
                  <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                    <GitPullRequest className="h-10 w-10" />
                  </div>
                </div>
                {/* Content */}
                <div className="p-6 lg:w-1/2 flex flex-col justify-center">
                  <h3 className="text-2xl font-semibold mb-2">{features[1].title}</h3>
                  <p className="text-base text-muted-foreground">{features[1].description}</p>
                </div>
              </div>
            </div>

            {/* Bottom Row - 3 Equal Cards */}
            {/* Card 3: Security Analysis */}
            <div className="group relative rounded-2xl border border-border/50 bg-card overflow-hidden transition-all hover:border-primary/50">
              {/* Illustration Area */}
              <div className="h-40 bg-muted/30 flex items-center justify-center border-b border-border/30">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                  <Shield className="h-8 w-8" />
                </div>
              </div>
              {/* Content */}
              <div className="p-6">
                <h3 className="text-xl font-semibold mb-2">{features[2].title}</h3>
                <p className="text-base text-muted-foreground">{features[2].description}</p>
              </div>
            </div>

            {/* Card 4: Multi-Language Support */}
            <div className="group relative rounded-2xl border border-border/50 bg-card overflow-hidden transition-all hover:border-primary/50">
              {/* Illustration Area */}
              <div className="h-40 bg-muted/30 flex items-center justify-center border-b border-border/30">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                  <Code2 className="h-8 w-8" />
                </div>
              </div>
              {/* Content */}
              <div className="p-6">
                <h3 className="text-xl font-semibold mb-2">{features[3].title}</h3>
                <p className="text-base text-muted-foreground">{features[3].description}</p>
              </div>
            </div>

            {/* Card 5: Custom Rules */}
            <div className="group relative rounded-2xl border border-border/50 bg-card overflow-hidden transition-all hover:border-primary/50">
              {/* Illustration Area */}
              <div className="h-40 bg-muted/30 flex items-center justify-center border-b border-border/30">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                  <Settings className="h-8 w-8" />
                </div>
              </div>
              {/* Content */}
              <div className="p-6">
                <h3 className="text-xl font-semibold mb-2">{features[4].title}</h3>
                <p className="text-base text-muted-foreground">{features[4].description}</p>
              </div>
            </div>

          </div>
        </section>

        {/* How It Works Section */}
        <section className="bg-muted/30 border-y border-border/40">
          <div className="container mx-auto px-12 md:px-24 lg:px-32 py-24">
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
        <section className="container mx-auto px-12 md:px-24 lg:px-32 py-24">
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

          <div className="container mx-auto px-12 md:px-24 lg:px-32 py-24">
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
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-border/40 bg-muted/10">
        <div className="container mx-auto px-12 md:px-24 lg:px-32 py-12">
          {/* Main Footer Content */}
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-12">
            {/* Brand Column */}
            <div className="shrink-0">
              <Link href="/" className="flex items-center gap-2">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary overflow-hidden">
                  <img src="/rabbit.svg" alt="Open Rabbit Logo" className="h-full w-full object-cover" />
                </div>
                <span className="font-bold text-xl">Open Rabbit</span>
              </Link>
            </div>

            {/* Link Columns - Flex with consistent gaps */}
            <div className="flex flex-wrap gap-20 lg:gap-28">
              {/* Community Column */}
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-4">Community</h4>
                <ul className="space-y-3 text-sm">
                  <li>
                    <Link href="#" className="flex items-center gap-2 text-foreground hover:text-primary transition-colors">
                      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" /></svg>
                      Become a member
                    </Link>
                  </li>
                  <li>
                    <Link href="#" className="flex items-center gap-2 text-foreground hover:text-primary transition-colors">
                      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" /></svg>
                      YouTube
                    </Link>
                  </li>
                  <li>
                    <Link href="#" className="flex items-center gap-2 text-foreground hover:text-primary transition-colors">
                      <Github className="h-4 w-4" />
                      GitHub
                    </Link>
                  </li>
                  <li>
                    <Link href="#" className="flex items-center gap-2 text-foreground hover:text-primary transition-colors">
                      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" /></svg>
                      LinkedIn
                    </Link>
                  </li>
                  <li>
                    <Link href="#" className="flex items-center gap-2 text-foreground hover:text-primary transition-colors">
                      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" /></svg>
                      Twitter / X
                    </Link>
                  </li>
                </ul>
              </div>

              {/* Company Column */}
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-4">Company</h4>
                <ul className="space-y-3 text-sm">
                  <li><Link href="#" className="text-foreground hover:text-primary transition-colors">About us</Link></li>
                  <li><Link href="#" className="text-foreground hover:text-primary transition-colors">Careers</Link></li>
                  <li><Link href="#" className="text-foreground hover:text-primary transition-colors">Contact</Link></li>
                  <li><Link href="#" className="text-foreground hover:text-primary transition-colors">Press</Link></li>
                </ul>
              </div>

              {/* Products Column */}
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-4">Products</h4>
                <ul className="space-y-3 text-sm">
                  <li><Link href="#" className="text-foreground hover:text-primary transition-colors">AI Code Reviews in Git</Link></li>
                  <li><Link href="#" className="text-foreground hover:text-primary transition-colors">AI Code Reviews in IDE</Link></li>
                </ul>
              </div>

              {/* Resources Column */}
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-4">Resources</h4>
                <ul className="space-y-3 text-sm">
                  <li><Link href="#" className="text-foreground hover:text-primary transition-colors">Documentation</Link></li>
                  <li><Link href="#" className="text-foreground hover:text-primary transition-colors">Status</Link></li>
                  <li><Link href="#" className="text-foreground hover:text-primary transition-colors">Blog</Link></li>
                  <li><Link href="#" className="text-foreground hover:text-primary transition-colors">Changelog</Link></li>
                  <li><Link href="#" className="text-foreground hover:text-primary transition-colors">Compare AI tools</Link></li>
                  <li><Link href="#" className="text-foreground hover:text-primary transition-colors">Security</Link></li>
                  <li><Link href="#" className="text-foreground hover:text-primary transition-colors">Trust Center</Link></li>
                  <li><Link href="#" className="text-foreground hover:text-primary transition-colors">Terms of Use</Link></li>
                  <li><Link href="#" className="text-foreground hover:text-primary transition-colors">Privacy Statement</Link></li>
                </ul>
              </div>
            </div>
          </div>

          {/* Bottom Copyright */}
          <div className="mt-12 pt-8 border-t border-border/40 text-sm text-muted-foreground">
            © 2025 Open Rabbit. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
}
