import { useState, useRef } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/Shared";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { UploadCloud, CheckCircle2, AlertTriangle, FileDown } from "lucide-react";
import { toast } from "sonner";

const SAMPLE = `imie,nazwisko,telefon,email,data_ostatniej_wizyty,typ_procedury
Anna,Nowak,+48 501 234 567,anna.nowak@example.com,2024-11-15,Higienizacja
Piotr,Kowalski,+48 602 345 678,piotr.k@example.com,15.10.2024,Kontrola / Przegląd
Maria,Wójcik,,maria@example.com,2024-06-01,Wybielanie`;

export default function ImportPage() {
  const [preview, setPreview] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef();

  const handleFile = async (file) => {
    if (!file) return;
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api.post("/patients/import/preview", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setPreview(r.data);
    } catch { toast.error("Nie udało się wczytać pliku"); }
    setUploading(false);
  };

  const commit = async () => {
    const r = await api.post("/patients/import/commit", { rows: preview.rows });
    toast.success(`Zaimportowano ${r.data.inserted} pacjentów — ${r.data.marked_due} do przypomnienia`);
    setPreview(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const downloadSample = () => {
    const blob = new Blob([SAMPLE], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "przyklad_pacjenci.csv"; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div data-testid="import-page">
      <PageHeader
        title="Import danych"
        subtitle="Wyeksportuj listę pacjentów ze swojego systemu (SmartDental, Dentidesk, Medfile) i wgraj plik CSV"
        action={<Button variant="outline" onClick={downloadSample} className="gap-2"><FileDown className="h-4 w-4" /> Przykładowy plik</Button>}
      />

      {!preview && (
        <Card className="shadow-none">
          <label
            data-testid="upload-dropzone"
            className="flex flex-col items-center justify-center gap-4 py-16 px-6 cursor-pointer border-2 border-dashed border-border rounded-xl m-4 hover:border-primary/50 hover:bg-secondary/30 transition-colors"
          >
            <div className="h-14 w-14 rounded-2xl bg-secondary flex items-center justify-center">
              <UploadCloud className="h-7 w-7 text-primary" />
            </div>
            <div className="text-center">
              <p className="font-medium">{uploading ? "Wczytywanie..." : "Kliknij, aby wybrać plik CSV"}</p>
              <p className="text-sm text-muted-foreground mt-1">Obsługiwane kolumny: imię, nazwisko, telefon, email, data ostatniej wizyty, typ procedury</p>
            </div>
            <input
              ref={fileRef}
              data-testid="file-input"
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => handleFile(e.target.files[0])}
            />
          </label>
        </Card>
      )}

      {preview && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <Card className="p-4 shadow-none"><div className="text-sm text-muted-foreground">Wszystkich wierszy</div><div className="font-head text-2xl font-bold">{preview.total}</div></Card>
            <Card className="p-4 shadow-none border-emerald-200 bg-emerald-50"><div className="text-sm text-emerald-700 flex items-center gap-1.5"><CheckCircle2 className="h-4 w-4" />Poprawnych</div><div className="font-head text-2xl font-bold text-emerald-700" data-testid="valid-count">{preview.valid}</div></Card>
            <Card className="p-4 shadow-none border-amber-200 bg-amber-50"><div className="text-sm text-amber-700 flex items-center gap-1.5"><AlertTriangle className="h-4 w-4" />Z błędami</div><div className="font-head text-2xl font-bold text-amber-700" data-testid="invalid-count">{preview.invalid}</div></Card>
          </div>

          <Card className="shadow-none overflow-hidden mb-4">
            <div className="overflow-x-auto max-h-[420px]">
              <Table>
                <TableHeader>
                  <TableRow className="bg-secondary/50">
                    <TableHead>Imię</TableHead><TableHead>Nazwisko</TableHead>
                    <TableHead>Telefon</TableHead><TableHead>Email</TableHead>
                    <TableHead>Ostatnia wizyta</TableHead><TableHead>Procedura</TableHead>
                    <TableHead>Walidacja</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {preview.rows.map((r, i) => (
                    <TableRow key={i} className={r._errors?.length ? "bg-amber-50/50" : ""}>
                      <TableCell>{r.imie}</TableCell>
                      <TableCell>{r.nazwisko}</TableCell>
                      <TableCell className="text-sm">{r.telefon}</TableCell>
                      <TableCell className="text-sm">{r.email}</TableCell>
                      <TableCell className="text-sm">{r.data_ostatniej_wizyty}</TableCell>
                      <TableCell className="text-sm">{r.typ_ostatniej_procedury}</TableCell>
                      <TableCell>
                        {r._errors?.length ? (
                          <span className="text-xs text-amber-700">{r._errors.join(", ")}</span>
                        ) : (
                          <span className="text-xs text-emerald-700 flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5" />OK</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Card>

          <div className="flex gap-3">
            <Button variant="outline" onClick={() => setPreview(null)}>Anuluj</Button>
            <Button data-testid="commit-import-btn" onClick={commit} disabled={preview.valid === 0}>
              Importuj {preview.valid} pacjentów
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
