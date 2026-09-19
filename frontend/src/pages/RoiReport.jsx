import { useEffect, useState } from "react";
import { api, zl } from "@/lib/api";
import { PageHeader } from "@/components/Shared";
import { Card } from "@/components/ui/card";
import { Send, CalendarCheck, XCircle, TrendingUp, Percent } from "lucide-react";
import { motion } from "framer-motion";

export default function RoiReport() {
  const [roi, setRoi] = useState(null);

  useEffect(() => { api.get("/roi").then((r) => setRoi(r.data)); }, []);

  const stats = roi ? [
    { label: "Wysłanych przypomnień", value: roi.przypomnienia, icon: Send, cls: "text-sky-600 bg-sky-50" },
    { label: "Pacjentów zapisanych", value: roi.zapisy, icon: CalendarCheck, cls: "text-emerald-600 bg-emerald-50" },
    { label: "Odrzuceń", value: roi.odrzucenia, icon: XCircle, cls: "text-rose-600 bg-rose-50" },
    { label: "Konwersja", value: `${roi.konwersja}%`, icon: Percent, cls: "text-amber-600 bg-amber-50" },
  ] : [];

  return (
    <div data-testid="roi-page">
      <PageHeader title="Raport ROI" subtitle="Podsumowanie ostatnich 30 dni — realna wartość odzyskanych pacjentów" />

      <motion.div
        initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl bg-primary text-primary-foreground p-8 mb-6"
      >
        <div className="flex items-center gap-2 text-sm opacity-80 mb-2">
          <TrendingUp className="h-4 w-4" /> Szacunkowy przychód z odzyskanych wizyt
        </div>
        <div className="font-head text-5xl font-bold" data-testid="roi-revenue">
          {roi ? zl(roi.szacunkowy_przychod) : "—"}
        </div>
        <p className="text-sm opacity-80 mt-3 max-w-xl">
          {roi && `W tym okresie przypomniano ${roi.przypomnienia} pacjentom, z czego ${roi.zapisy} zapisało się na wizytę. `}
          Jeden odzyskany pacjent często zwraca roczny koszt subskrypcji.
        </p>
      </motion.div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s, i) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}>
            <Card className="p-5 shadow-none">
              <div className={`h-10 w-10 rounded-xl flex items-center justify-center mb-3 ${s.cls}`}>
                <s.icon className="h-5 w-5" />
              </div>
              <div className="font-head text-3xl font-bold" data-testid={`roi-stat-${i}`}>{s.value}</div>
              <div className="text-sm text-muted-foreground mt-1">{s.label}</div>
            </Card>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
