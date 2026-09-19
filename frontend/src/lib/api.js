import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

export const STATUS_META = {
  AKTYWNY: { label: "Aktywny", color: "text-stone-600", bg: "bg-stone-100", dot: "bg-stone-400" },
  DO_PRZYPOMNIENIA: { label: "Do przypomnienia", color: "text-amber-700", bg: "bg-amber-100", dot: "bg-amber-500" },
  PRZYPOMNIANY: { label: "Przypomniano", color: "text-sky-700", bg: "bg-sky-100", dot: "bg-sky-500" },
  ZAPISANY: { label: "Zapisano", color: "text-emerald-700", bg: "bg-emerald-100", dot: "bg-emerald-500" },
  ODRZUCONY: { label: "Odrzucono", color: "text-rose-700", bg: "bg-rose-100", dot: "bg-rose-500" },
};

export const zl = (n) => new Intl.NumberFormat("pl-PL").format(n || 0) + " zł";
