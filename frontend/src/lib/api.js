import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;
export const TOKEN_KEY = "recalldent_token";

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && !err.config?.url?.startsWith("/auth/")) {
      localStorage.removeItem(TOKEN_KEY);
      if (!window.location.pathname.startsWith("/logowanie")) window.location.assign("/logowanie");
    }
    return Promise.reject(err);
  }
);

export const apiError = (e, fallback = "Coś poszło nie tak. Spróbuj ponownie.") => {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || fallback;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => (typeof x?.msg === "string" ? x.msg : JSON.stringify(x))).join(" ");
  return String(d);
};

export const STATUS_META = {
  AKTYWNY: { label: "Aktywny", color: "text-stone-600", bg: "bg-stone-100", dot: "bg-stone-400" },
  DO_PRZYPOMNIENIA: { label: "Do przypomnienia", color: "text-amber-700", bg: "bg-amber-100", dot: "bg-amber-500" },
  PRZYPOMNIANY: { label: "Przypomniano", color: "text-sky-700", bg: "bg-sky-100", dot: "bg-sky-500" },
  ZAPISANY: { label: "Zapisano", color: "text-emerald-700", bg: "bg-emerald-100", dot: "bg-emerald-500" },
  ODRZUCONY: { label: "Odrzucono", color: "text-rose-700", bg: "bg-rose-100", dot: "bg-rose-500" },
};

export const zl = (n) => new Intl.NumberFormat("pl-PL").format(n || 0) + " zł";
