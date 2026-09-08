import { useEffect, useState } from "react";
import { joinPath } from "@/lib/workspaceFiles";
import { Button, Dialog, SelectField, TextField } from "@/ui";

export type NotebookLanguage = "python" | "sql";

interface Props {
  open: boolean;
  defaultDir: string;
  onClose: () => void;
  onCreate: (path: string, language: NotebookLanguage) => void;
}

export function CreateNotebookDialog({ open, defaultDir, onClose, onCreate }: Props) {
  const [name, setName] = useState("");
  const [location, setLocation] = useState(defaultDir);
  const [language, setLanguage] = useState<NotebookLanguage>("python");

  useEffect(() => {
    if (open) {
      setName("");
      setLocation(defaultDir);
      setLanguage("python");
    }
  }, [open, defaultDir]);

  const submit = () => {
    const raw = name.trim();
    if (!raw) return;
    const file = raw.toLowerCase().endsWith(".ipynb") ? raw : `${raw}.ipynb`;
    onCreate(joinPath(location.trim().replace(/\/+$/, ""), file), language);
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Criar notebook"
      footer={
        <>
          <Button variant="text" onClick={onClose}>
            Cancelar
          </Button>
          <Button disabled={!name.trim()} onClick={submit}>
            Criar
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <TextField
          label="Nome"
          value={name}
          autoFocus
          placeholder="customer_etl"
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        <TextField
          label="Local"
          value={location}
          placeholder="notebooks/"
          onChange={(e) => setLocation(e.target.value)}
        />
        <SelectField
          label="Linguagem"
          value={language}
          onChange={(e) => setLanguage(e.target.value as NotebookLanguage)}
        >
          <option value="python">Python</option>
          <option value="sql">SQL</option>
        </SelectField>
      </div>
    </Dialog>
  );
}
