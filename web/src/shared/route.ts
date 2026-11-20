import { useEffect, useState } from "react";

export type View = "promise" | "day" | "decisions" | "warehouse";
export const VIEWS: View[] = ["promise", "day", "decisions", "warehouse"];

function read(): View {
  const [, v] = window.location.hash.split("/");
  return VIEWS.includes(v as View) ? (v as View) : "promise";
}

export function useRoute(): View {
  const [r, setR] = useState(read);
  useEffect(() => {
    const on = () => setR(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return r;
}

export const go = (view: View) => {
  window.location.hash = `/${view}`;
};
