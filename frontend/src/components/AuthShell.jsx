import { Stethoscope } from "lucide-react";
import { Link } from "react-router-dom";

export default function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background">
      <div className="hidden lg:flex flex-col justify-between p-12 bg-primary text-primary-foreground">
        <Link to="/" className="flex items-center gap-2.5">
          <div className="h-10 w-10 rounded-xl bg-white/15 flex items-center justify-center">
            <Stethoscope className="h-5 w-5" />
          </div>
          <span className="font-head font-bold text-lg">RecallDent</span>
        </Link>
        <div className="max-w-md">
          <h2 className="font-head text-4xl font-bold leading-tight mb-4">
            Pacjenci wracają sami. Recepcja odpoczywa.
          </h2>
          <p className="text-primary-foreground/80 text-base leading-relaxed">
            Automatyczne przypomnienia SMS i email o wizytach kontrolnych, zapis online bez telefonów
            i raport ROI w jednym panelu gabinetu.
          </p>
        </div>
        <div className="text-xs text-primary-foreground/60">© {new Date().getFullYear()} RecallDent — recall dla gabinetów stomatologicznych</div>
      </div>
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="h-9 w-9 rounded-xl bg-primary flex items-center justify-center">
              <Stethoscope className="h-5 w-5 text-primary-foreground" />
            </div>
            <span className="font-head font-bold">RecallDent</span>
          </div>
          <h1 className="font-head text-3xl font-bold tracking-tight mb-1">{title}</h1>
          <p className="text-muted-foreground text-sm mb-8">{subtitle}</p>
          {children}
          {footer && <div className="mt-6 text-sm text-muted-foreground text-center">{footer}</div>}
        </div>
      </div>
    </div>
  );
}
