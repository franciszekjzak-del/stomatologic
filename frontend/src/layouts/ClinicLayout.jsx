import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import {
  LayoutDashboard, Users, Upload, Clock, MessageSquareText,
  TrendingUp, Inbox, Settings, Stethoscope, Play, RotateCcw, CalendarClock,
} from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

const NAV = [
  { to: "/panel", label: "Dashboard", icon: LayoutDashboard, id: "dashboard" },
  { to: "/pacjenci", label: "Lista pacjentów", icon: Users, id: "patients" },
  { to: "/import", label: "Import danych", icon: Upload, id: "import" },
  { to: "/terminy", label: "Dostępne terminy", icon: CalendarClock, id: "slots" },
  { to: "/ustawienia-recallu", label: "Ustawienia recallu", icon: Clock, id: "recall" },
  { to: "/szablony", label: "Szablony wiadomości", icon: MessageSquareText, id: "templates" },
  { to: "/wiadomosci", label: "Wysłane wiadomości", icon: Inbox, id: "messages" },
  { to: "/raport-roi", label: "Raport ROI", icon: TrendingUp, id: "roi" },
  { to: "/ustawienia", label: "Ustawienia gabinetu", icon: Settings, id: "settings" },
];

export default function ClinicLayout() {
  const [clinic, setClinic] = useState({ nazwa_gabinetu: "", plan: "" });
  const navigate = useNavigate();

  const load = () => api.get("/settings").then((r) => setClinic(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const runScan = async () => {
    const r = await api.post("/recall/run");
    toast.success(`Skanowanie zakończone — ${r.data.marked_due} nowych pacjentów do przypomnienia`);
  };

  const resetDemo = async () => {
    await api.post("/admin/reset-demo");
    toast.success("Dane demonstracyjne zresetowane");
    navigate(0);
  };

  return (
    <div className="min-h-screen flex bg-background">
      <aside className="w-64 shrink-0 border-r border-border bg-card hidden lg:flex flex-col fixed h-screen">
        <div className="px-6 py-6 border-b border-border">
          <div className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-xl bg-primary flex items-center justify-center">
              <Stethoscope className="h-5 w-5 text-primary-foreground" />
            </div>
            <div>
              <div className="font-head font-bold text-[15px] leading-tight">RecallDent</div>
              <div className="text-[11px] text-muted-foreground">Automatyczny recall</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              data-testid={`nav-${n.id}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-primary text-primary-foreground font-medium"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                }`
              }
            >
              <n.icon className="h-[18px] w-[18px]" />
              {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-border space-y-2">
          <Button data-testid="run-scan-btn" onClick={runScan} className="w-full justify-start gap-2" size="sm">
            <Play className="h-4 w-4" /> Uruchom skanowanie
          </Button>
          <Button data-testid="reset-demo-btn" onClick={resetDemo} variant="ghost" size="sm"
            className="w-full justify-start gap-2 text-muted-foreground">
            <RotateCcw className="h-4 w-4" /> Reset demo
          </Button>
        </div>
      </aside>

      <div className="flex-1 lg:ml-64 min-w-0">
        <header className="h-16 border-b border-border bg-card/80 backdrop-blur sticky top-0 z-20 flex items-center justify-between px-6">
          <div className="font-head font-semibold text-foreground truncate" data-testid="clinic-name">
            {clinic.nazwa_gabinetu || "Gabinet"}
          </div>
          <span className="text-xs px-3 py-1 rounded-full bg-accent/20 text-accent-foreground font-medium">
            Plan {clinic.plan}
          </span>
        </header>
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
