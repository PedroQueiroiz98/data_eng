import { useTheme, type ThemePref } from "@/components/ThemeProvider";
import { IconButton } from "@/ui/IconButton";
import { DarkIcon, LightIcon, SystemIcon } from "@/ui/icons";

const NEXT: Record<ThemePref, ThemePref> = {
  light: "dark",
  dark: "system",
  system: "light",
};

const LABEL: Record<ThemePref, string> = {
  light: "Tema: claro",
  dark: "Tema: escuro",
  system: "Tema: sistema",
};

/** Botão único que alterna claro → escuro → sistema. */
export function ThemeToggle() {
  const { pref, setPref } = useTheme();
  const Icon = pref === "light" ? LightIcon : pref === "dark" ? DarkIcon : SystemIcon;
  return (
    <IconButton
      label={`${LABEL[pref]} (clique para alternar)`}
      icon={<Icon className="h-5 w-5" />}
      onClick={() => setPref(NEXT[pref])}
    />
  );
}
