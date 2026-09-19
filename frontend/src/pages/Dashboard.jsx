import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/Shared";
import { Card } from "@/components/ui/card";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { AlertCircle, Send, CalendarCheck, XCircle, Users } from "lucide-react";
import { motion } from "framer-motion";

const TILES = [
  { key: "DO_PRZYPOMNIENIA", label: "Do przypomnienia", icon: AlertCircle, cls: "text-amber-600 bg-amber-50 border-amber-200" },
  { key: "PRZYPOMNIANY", label: "Przypomniano", icon: Send, cls: "text-sky-600 bg-sky-50 border-sky-200" },
  { key: "ZAPISANY", label: "Zapisano", icon: CalendarCheck, cls: "text-emerald-600 bg-emerald-50 border-emerald-200" },
  { key: "ODRZUCONY", label: "Odrzucono", icon: XCircle, cls: "text-rose-600 bg-rose-50 border-rose-200" },
];

export default function Dashboard() {
  const [data, setData] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/dashboard/stats").then((r) => setData(r.data));
  }, []);

  const fmtDay = (d) => {
    const dt = new Date(d);
    return `${dt.getDate()}.${dt.getMonth() + 1}`;
  };

  return (
    <div data-testid="dashboard-page">
      <PageHeader
        title="Dashboard"
        subtitle="Przegląd statusu recallu pacjentów w Twoim gabinecie"
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {TILES.map((t, i) => (
          <motion.button
            key={t.key}
            data-testid={`tile-${t.key}`}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            onClick={() => navigate(`/pacjenci?status=${t.key}`)}
            className="text-left"
          >
            <Card className={`p-5 border hover:-translate-y-0.5 transition-transform ${t.cls}`}>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium">{t.label}</span>
                <t.icon className="h-5 w-5 opacity-70" />
              </div>
              <div className="font-head text-4xl font-bold" data-testid={`tile-count-${t.key}`}>
                {data ? data.counts[t.key] : "—"}
              </div>
            </Card>
          </motion.button>
        ))}
      </div>

      <Card className="p-5 mb-6 shadow-none">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-head font-semibold text-lg">Przypomnienia vs zapisy</h3>
            <p className="text-xs text-muted-foreground">Ostatnie 30 dni</p>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-[hsl(var(--chart-1))]" />Przypomnienia</span>
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-[hsl(var(--chart-2))]" />Zapisy</span>
          </div>
        </div>
        <div className="h-72">
          {data && (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.chart} margin={{ left: -20, right: 8, top: 8 }}>
                <defs>
                  <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(var(--chart-1))" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="hsl(var(--chart-1))" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="g2" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(var(--chart-2))" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="hsl(var(--chart-2))" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis dataKey="data" tickFormatter={fmtDay} tick={{ fontSize: 11 }} interval={4} stroke="hsl(var(--muted-foreground))" />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} stroke="hsl(var(--muted-foreground))" />
                <Tooltip
                  labelFormatter={fmtDay}
                  contentStyle={{ borderRadius: 12, border: "1px solid hsl(var(--border))", fontSize: 12 }}
                />
                <Area type="monotone" dataKey="przypomnienia" name="Przypomnienia" stroke="hsl(var(--chart-1))" fill="url(#g1)" strokeWidth={2} />
                <Area type="monotone" dataKey="zapisy" name="Zapisy" stroke="hsl(var(--chart-2))" fill="url(#g2)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>

      <Card className="p-5 shadow-none flex items-center gap-4">
        <div className="h-11 w-11 rounded-xl bg-secondary flex items-center justify-center">
          <Users className="h-5 w-5 text-primary" />
        </div>
        <div>
          <div className="text-sm text-muted-foreground">Łączna liczba pacjentów w bazie</div>
          <div className="font-head text-2xl font-bold" data-testid="total-patients">{data ? data.total : "—"}</div>
        </div>
      </Card>
    </div>
  );
}
