import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, BarChart3, Info, Network } from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { api } from "../api/client";
import { cn } from "../lib/cn";
import { Chip } from "./ui/Badge";

interface LayoutProps {
  children: ReactNode;
}

const navItems = [
  { to: "/", label: "Analyze", icon: Network },
  { to: "/report", label: "Model Report", icon: BarChart3 },
  { to: "/about", label: "About", icon: Info },
];

function NodeTreeLogo() {
  return (
    <svg
      viewBox="0 0 28 28"
      className="h-7 w-7 shrink-0"
      aria-hidden="true"
      fill="none"
    >
      <rect width="28" height="28" rx="8" fill="rgba(79, 140, 255, 0.14)" />
      <path
        d="M14 7L8.5 14.5M14 7L19.5 14.5M8.5 14.5L6.5 21M8.5 14.5L11.5 21M19.5 14.5L21.5 21"
        stroke="#4F8CFF"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <circle cx="14" cy="7" r="2.4" fill="#22D3EE" />
      <circle cx="8.5" cy="14.5" r="2" fill="#4F8CFF" />
      <circle cx="19.5" cy="14.5" r="2" fill="#4F8CFF" />
      <circle cx="6.5" cy="21" r="1.6" fill="#38BDF8" />
      <circle cx="11.5" cy="21" r="1.6" fill="#38BDF8" />
      <circle cx="21.5" cy="21" r="1.6" fill="#F59E0B" />
    </svg>
  );
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: () => api.getHealth(),
    retry: false,
    staleTime: 60_000,
  });

  const health = healthQuery.data;
  const showDisclaimer = location.pathname === "/" || location.pathname === "/report";

  return (
    <div className="observatory-canvas relative min-h-screen text-text-1 flex">
      <div
        aria-hidden="true"
        className="observatory-grid pointer-events-none fixed inset-0 opacity-[0.04]"
      />

      {/* Desktop slim left rail (64px -> 220px on hover/focus-within) */}
      <aside
        aria-label="Workspace navigation"
        className="group/rail fixed inset-y-0 left-0 z-30 hidden w-16 flex-col border-r border-subtle bg-bg-1/95 backdrop-blur-md transition-[width] duration-200 hover:w-[220px] focus-within:w-[220px] md:flex"
      >
        <div className="flex h-16 items-center gap-3 border-b border-subtle px-4 overflow-hidden">
          <NodeTreeLogo />
          <span className="whitespace-nowrap font-display text-sm font-semibold tracking-tight text-text-1 opacity-0 transition-opacity duration-150 group-hover/rail:opacity-100 group-focus-within/rail:opacity-100">
            Cascade Lab
          </span>
        </div>

        <nav aria-label="Primary navigation" className="flex-1 space-y-1.5 p-2.5">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cn(
                  "relative flex h-10 items-center gap-3 overflow-hidden rounded-xl px-2.5 text-sm font-medium transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg-1",
                  isActive
                    ? "bg-accent/15 text-text-1"
                    : "text-text-2 hover:bg-bg-2/80 hover:text-text-1"
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span
                      aria-hidden="true"
                      className="absolute inset-y-2 left-0 w-[3px] rounded-r-full bg-accent"
                    />
                  )}
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0 ml-0.5",
                      isActive ? "text-accent-2" : "text-text-2"
                    )}
                    strokeWidth={1.5}
                    aria-hidden="true"
                  />
                  <span className="whitespace-nowrap opacity-0 transition-opacity duration-150 group-hover/rail:opacity-100 group-focus-within/rail:opacity-100">
                    {label}
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-subtle p-3 text-[11px] text-text-3 overflow-hidden">
          <p className="whitespace-nowrap opacity-0 transition-opacity duration-150 group-hover/rail:opacity-100 group-focus-within/rail:opacity-100">
            Structure &amp; timing only
          </p>
        </div>
      </aside>

      {/* Main shell */}
      <div className="relative z-10 flex min-h-screen w-full flex-col pb-16 md:pb-0 md:pl-16">
        <header className="glass-surface sticky top-0 z-20 border-x-0 border-t-0">
          <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
            <div className="flex items-center gap-3">
              <div className="md:hidden">
                <NodeTreeLogo />
              </div>
              <div>
                <h1 className="font-display text-base font-semibold tracking-[-0.02em] text-text-1 sm:text-lg">
                  Cascade Virality Predictor
                </h1>
                <p className="text-xs text-text-3">
                  Early propagation structure observatory
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {health?.active_dataset && (
                <Chip variant="neutral" aria-label={`Active dataset ${health.active_dataset}`}>
                  Dataset: {health.active_dataset}
                </Chip>
              )}

              {health && (
                <Chip variant={health.model_loaded ? "success" : "viral"}>
                  <span
                    aria-hidden="true"
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      health.model_loaded ? "bg-success" : "bg-viral"
                    )}
                  />
                  {health.model_loaded ? "Model ready" : "Not trained"}
                </Chip>
              )}
            </div>
          </div>

          {showDisclaimer && (
            <div
              role="note"
              className="border-t border-subtle bg-bg-0/70 px-4 py-1.5 text-xs text-text-2 sm:px-6"
            >
              <div className="mx-auto flex max-w-[1440px] items-center justify-center gap-2 text-center">
                <AlertTriangle
                  className="h-3.5 w-3.5 shrink-0 text-accent-2"
                  strokeWidth={1.5}
                  aria-hidden="true"
                />
                <span>
                  Predicts spreading behaviour, not truthfulness. Uses early graph structure and
                  edge timestamps only.
                </span>
              </div>
            </div>
          )}
        </header>

        <main
          key={location.pathname}
          className="animate-route-enter mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 sm:px-6"
        >
          {children}
        </main>
      </div>

      {/* Mobile bottom tab bar */}
      <nav
        aria-label="Mobile navigation"
        className="glass-surface fixed inset-x-0 bottom-0 z-40 flex items-center justify-around border-x-0 border-b-0 py-1.5 md:hidden"
      >
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center gap-1 rounded-xl px-4 py-1.5 text-[11px] font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
                isActive ? "text-accent-2" : "text-text-2 hover:text-text-1"
              )
            }
          >
            <Icon className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
