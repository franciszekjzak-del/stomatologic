import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import ClinicLayout from "@/layouts/ClinicLayout";
import Dashboard from "@/pages/Dashboard";
import Patients from "@/pages/Patients";
import ImportPage from "@/pages/ImportPage";
import SlotsPage from "@/pages/SlotsPage";
import RecallSettings from "@/pages/RecallSettings";
import Templates from "@/pages/Templates";
import RoiReport from "@/pages/RoiReport";
import Messages from "@/pages/Messages";
import ClinicSettings from "@/pages/ClinicSettings";
import PatientBooking from "@/pages/PatientBooking";
import Login from "@/pages/Login";
import Register from "@/pages/Register";

function Protected() {
  const { user } = useAuth();
  if (user === null) {
    return <div className="min-h-screen flex items-center justify-center text-muted-foreground text-sm" data-testid="auth-loading">Ładowanie...</div>;
  }
  if (!user) return <Navigate to="/logowanie" replace />;
  return <Outlet />;
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/zapis/:pid" element={<PatientBooking />} />
            <Route path="/logowanie" element={<Login />} />
            <Route path="/rejestracja" element={<Register />} />
            <Route element={<Protected />}>
              <Route element={<ClinicLayout />}>
                <Route path="/" element={<Navigate to="/panel" replace />} />
                <Route path="/panel" element={<Dashboard />} />
                <Route path="/pacjenci" element={<Patients />} />
                <Route path="/import" element={<ImportPage />} />
                <Route path="/terminy" element={<SlotsPage />} />
                <Route path="/ustawienia-recallu" element={<RecallSettings />} />
                <Route path="/szablony" element={<Templates />} />
                <Route path="/raport-roi" element={<RoiReport />} />
                <Route path="/wiadomosci" element={<Messages />} />
                <Route path="/ustawienia" element={<ClinicSettings />} />
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
      <Toaster position="top-right" richColors />
    </div>
  );
}

export default App;
