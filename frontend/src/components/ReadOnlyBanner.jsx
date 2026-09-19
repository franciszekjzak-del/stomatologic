import { useAuth } from "@/context/AuthContext";
import { Lock } from "lucide-react";

export const useIsOwner = () => useAuth()?.user?.rola === "owner";

export default function ReadOnlyBanner() {
  const isOwner = useIsOwner();
  if (isOwner) return null;
  return (
    <div data-testid="readonly-banner" className="mb-4 rounded-xl border border-amber-200 bg-amber-50 text-amber-800 p-3 text-sm flex items-center gap-2.5">
      <Lock className="h-4 w-4 shrink-0" /> Tryb podglądu — zmiany w tej sekcji może zapisywać tylko właściciel gabinetu.
    </div>
  );
}
