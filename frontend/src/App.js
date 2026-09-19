import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import ClinicLayout from "@/layouts/ClinicLayout";
import Dashboard from "@/pages/Dashboard";
import Patients from "@/pages/Patients";
import ImportPage from "@/pages/ImportPage";
import RecallSettings from "@/pages/RecallSettings";
import Templates from "@/pages/Templates";
import RoiReport from "@/pages/RoiReport";
import Messages from "@/pages/Messages";
import ClinicSettings from "@/pages/ClinicSettings";
import PatientBooking from "@/pages/PatientBooking";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/zapis/:pid" element={<PatientBooking />} />
          <Route element={<ClinicLayout />}>
            <Route path="/" element={<Navigate to="/panel" replace />} />
            <Route path="/panel" element={<Dashboard />} />
            <Route path="/pacjenci" element={<Patients />} />
            <Route path="/import" element={<ImportPage />} />
            <Route path="/ustawienia-recallu" element={<RecallSettings />} />
            <Route path="/szablony" element={<Templates />} />
            <Route path="/raport-roi" element={<RoiReport />} />
            <Route path="/wiadomosci" element={<Messages />} />
            <Route path="/ustawienia" element={<ClinicSettings />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </div>
  );
}

export default App;
